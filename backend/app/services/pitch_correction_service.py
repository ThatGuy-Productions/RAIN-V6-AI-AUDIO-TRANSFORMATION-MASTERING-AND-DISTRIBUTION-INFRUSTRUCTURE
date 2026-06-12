"""Vocal pitch analysis and correction service.

The analyzer uses CREPE when available and falls back to librosa.pyin for CPU
deployments. Processing uses WORLD vocoding so pitch changes preserve timing
and spectral envelope/formants instead of resampling the whole file.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal
import io
import math
import tempfile
import uuid

import numpy as np
import soundfile as sf
import structlog

logger = structlog.get_logger()

CorrectionMode = Literal["transparent", "natural", "aggressive"]

_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_SCALES = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
}
_MODE_DEFAULTS: dict[CorrectionMode, tuple[float, float, float]] = {
    "transparent": (0.35, 0.28, 0.75),
    "natural": (0.65, 0.14, 0.45),
    "aggressive": (0.95, 0.04, 0.15),
}


class PitchCorrectionError(RuntimeError):
    """Raised when analysis or correction cannot be completed."""


@dataclass(frozen=True)
class PitchFrame:
    time: float
    frequency_hz: float | None
    note: str | None
    cents_error: float | None
    confidence: float


@dataclass(frozen=True)
class PitchAnalysis:
    detected_key: str
    detected_scale: str
    voiced_ratio: float
    median_pitch_hz: float | None
    pitch_drift_cents: float
    vibrato_rate_hz: float
    vibrato_depth_cents: float
    note_histogram: dict[str, int]
    frames: list[PitchFrame]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["frames"] = [asdict(frame) for frame in self.frames]
        return data


@dataclass(frozen=True)
class PitchProcessResult:
    job_id: str
    output_path: str
    report_path: str
    detected_key: str
    detected_scale: str
    statistics: dict[str, float | int | str]


def _read_audio_bytes(audio_data: bytes) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(io.BytesIO(audio_data), dtype="float64", always_2d=True)
    if audio.size == 0:
        raise PitchCorrectionError("Uploaded audio is empty")
    if not np.isfinite(audio).all():
        raise PitchCorrectionError("Uploaded audio contains non-finite samples")
    return audio, int(sr)


def _midi_to_name(midi: float) -> str:
    rounded = int(round(midi))
    return f"{_NOTE_NAMES[rounded % 12]}{rounded // 12 - 1}"


def _hz_to_midi(frequency: np.ndarray | float) -> np.ndarray | float:
    return 69.0 + 12.0 * np.log2(np.maximum(frequency, 1e-9) / 440.0)


def _midi_to_hz(midi: np.ndarray | float) -> np.ndarray | float:
    return 440.0 * np.power(2.0, (midi - 69.0) / 12.0)


def _nearest_scale_midi(midi: np.ndarray, tonic_pc: int, scale: str) -> np.ndarray:
    scale_pcs = np.array(_SCALES[scale], dtype=np.float64)
    base_octave = np.floor(midi / 12.0) * 12.0 + tonic_pc
    candidates = []
    for octave_shift in (-12.0, 0.0, 12.0):
        candidates.append(base_octave[:, None] + scale_pcs[None, :] + octave_shift)
    matrix = np.concatenate(candidates, axis=1)
    nearest_idx = np.argmin(np.abs(matrix - midi[:, None]), axis=1)
    return matrix[np.arange(len(midi)), nearest_idx]


def _estimate_pitch(mono: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return times, f0_hz with nan for unvoiced, confidence."""
    try:
        import crepe

        step_size_ms = 10
        times, frequency, confidence, _ = crepe.predict(
            mono.astype(np.float32),
            sr,
            step_size=step_size_ms,
            model_capacity="full",
            viterbi=True,
            verbose=0,
        )
        frequency = frequency.astype(np.float64)
        confidence = confidence.astype(np.float64)
        frequency[confidence < 0.45] = np.nan
        return times.astype(np.float64), frequency, confidence
    except Exception as exc:  # noqa: BLE001
        logger.info("crepe_unavailable_using_pyin", reason=str(exc))

    import librosa

    hop_length = max(128, int(sr * 0.01))
    f0, voiced_flag, voiced_prob = librosa.pyin(
        mono,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
        hop_length=hop_length,
    )
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)
    confidence = np.where(voiced_flag, voiced_prob, 0.0)
    f0 = np.where(voiced_flag, f0, np.nan)
    return times.astype(np.float64), f0.astype(np.float64), confidence.astype(np.float64)


def _detect_key_scale(mono: np.ndarray, sr: int) -> tuple[str, str]:
    import librosa

    chroma = librosa.feature.chroma_cqt(y=mono.astype(np.float32), sr=sr)
    profile = np.mean(chroma, axis=1)
    if np.max(profile) > 0:
        profile = profile / np.max(profile)

    best_key = "C"
    best_scale = "major"
    best_score = -math.inf
    major_template = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    minor_template = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    for tonic in range(12):
        for scale, template in (("major", major_template), ("minor", minor_template)):
            rotated = np.roll(template, tonic)
            score = float(np.corrcoef(profile, rotated)[0, 1])
            if np.isfinite(score) and score > best_score:
                best_score = score
                best_key = _NOTE_NAMES[tonic]
                best_scale = scale
    return best_key, best_scale


def analyze_pitch(audio_data: bytes) -> PitchAnalysis:
    audio, sr = _read_audio_bytes(audio_data)
    mono = np.mean(audio, axis=1)
    times, f0, confidence = _estimate_pitch(mono, sr)
    voiced = np.isfinite(f0) & (f0 > 0.0)
    detected_key, detected_scale = _detect_key_scale(mono, sr)

    frames: list[PitchFrame] = []
    note_histogram: dict[str, int] = {}
    cents_errors: list[float] = []
    midi_voiced = _hz_to_midi(f0[voiced]) if np.any(voiced) else np.array([])
    rounded = np.round(midi_voiced) if len(midi_voiced) else np.array([])
    cents = (midi_voiced - rounded) * 100.0 if len(midi_voiced) else np.array([])

    if len(cents):
        cents_errors = [float(x) for x in cents]

    voiced_iter = iter(cents)
    for t, hz, conf in zip(times, f0, confidence):
        if np.isfinite(hz) and hz > 0:
            midi = float(_hz_to_midi(float(hz)))
            name = _midi_to_name(midi)
            note_histogram[name[:-1]] = note_histogram.get(name[:-1], 0) + 1
            cents_error = float(next(voiced_iter))
            frames.append(PitchFrame(float(t), float(hz), name, cents_error, float(conf)))
        else:
            frames.append(PitchFrame(float(t), None, None, None, float(conf)))

    vibrato_rate, vibrato_depth = _vibrato_stats(times[voiced], cents if len(cents) else np.array([]))
    drift = float(np.std(cents_errors)) if cents_errors else 0.0
    median_pitch = float(np.median(f0[voiced])) if np.any(voiced) else None

    logger.info(
        "pitch_analysis_complete",
        key=detected_key,
        scale=detected_scale,
        voiced_ratio=float(np.mean(voiced)) if len(voiced) else 0.0,
    )
    return PitchAnalysis(
        detected_key=detected_key,
        detected_scale=detected_scale,
        voiced_ratio=float(np.mean(voiced)) if len(voiced) else 0.0,
        median_pitch_hz=median_pitch,
        pitch_drift_cents=drift,
        vibrato_rate_hz=vibrato_rate,
        vibrato_depth_cents=vibrato_depth,
        note_histogram=note_histogram,
        frames=frames,
    )


def _vibrato_stats(times: np.ndarray, cents: np.ndarray) -> tuple[float, float]:
    if len(times) < 8 or len(cents) < 8:
        return 0.0, 0.0
    centered = cents - np.median(cents)
    depth = float(np.percentile(np.abs(centered), 75))
    dt = float(np.median(np.diff(times)))
    if dt <= 0:
        return 0.0, depth
    spectrum = np.abs(np.fft.rfft(centered * np.hanning(len(centered))))
    freqs = np.fft.rfftfreq(len(centered), dt)
    mask = (freqs >= 3.0) & (freqs <= 9.0)
    if not np.any(mask):
        return 0.0, depth
    rate = float(freqs[mask][np.argmax(spectrum[mask])])
    return rate, depth


def process_pitch(
    audio_data: bytes,
    mode: CorrectionMode = "natural",
    strength: float | None = None,
    retune_speed: float | None = None,
    humanization: float | None = None,
    key: str | None = None,
    scale: str | None = None,
    preview_seconds: float | None = None,
) -> PitchProcessResult:
    try:
        import pyworld
    except ImportError as exc:
        raise PitchCorrectionError("pyworld is required for formant-preserving pitch correction") from exc

    audio, sr = _read_audio_bytes(audio_data)
    if preview_seconds:
        audio = audio[: int(sr * preview_seconds)]

    analysis = analyze_pitch(audio_data if preview_seconds is None else _write_temp_bytes(audio, sr))
    detected_key = key or analysis.detected_key
    detected_scale = scale or analysis.detected_scale
    if detected_key not in _NOTE_NAMES:
        raise PitchCorrectionError(f"Unsupported key: {detected_key}")
    if detected_scale not in _SCALES:
        raise PitchCorrectionError(f"Unsupported scale: {detected_scale}")

    default_strength, default_speed, default_human = _MODE_DEFAULTS[mode]
    strength = float(np.clip(default_strength if strength is None else strength, 0.0, 1.0))
    retune_speed = float(np.clip(default_speed if retune_speed is None else retune_speed, 0.01, 1.0))
    humanization = float(np.clip(default_human if humanization is None else humanization, 0.0, 1.0))

    output_channels = []
    correction_cents: list[float] = []
    tonic = _NOTE_NAMES.index(detected_key)

    for channel in range(audio.shape[1]):
        x = np.ascontiguousarray(audio[:, channel].astype(np.float64))
        frame_period = 5.0
        f0, time_axis = pyworld.dio(x, sr, frame_period=frame_period)
        f0 = pyworld.stonemask(x, f0, time_axis, sr)
        spectral_envelope = pyworld.cheaptrick(x, f0, time_axis, sr)
        aperiodicity = pyworld.d4c(x, f0, time_axis, sr)

        voiced = f0 > 0
        corrected_f0 = f0.copy()
        if np.any(voiced):
            midi = _hz_to_midi(f0[voiced])
            target_midi = _nearest_scale_midi(midi, tonic, detected_scale)
            correction = (target_midi - midi) * strength * (1.0 - 0.75 * humanization)
            correction = _smooth_correction(correction, retune_speed)
            corrected_f0[voiced] = _midi_to_hz(midi + correction)
            correction_cents.extend([float(c * 100.0) for c in correction])

        y = pyworld.synthesize(corrected_f0, spectral_envelope, aperiodicity, sr, frame_period=frame_period)
        output_channels.append(y[: audio.shape[0]])

    length = min(len(ch) for ch in output_channels)
    output = np.column_stack([ch[:length] for ch in output_channels]).astype(np.float32)
    peak = float(np.max(np.abs(output))) if output.size else 0.0
    if peak > 0.999:
        output = output / peak * 0.999

    job_id = str(uuid.uuid4())
    out_dir = Path(tempfile.gettempdir()) / "rain_pitch_correction"
    out_dir.mkdir(exist_ok=True)
    output_path = str(out_dir / f"{job_id}_corrected.wav")
    report_path = str(out_dir / f"{job_id}_report.json")
    sf.write(output_path, output, sr, subtype="PCM_24")

    stats = {
        "mode": mode,
        "strength": strength,
        "retune_speed": retune_speed,
        "humanization": humanization,
        "mean_correction_cents": float(np.mean(np.abs(correction_cents))) if correction_cents else 0.0,
        "max_correction_cents": float(np.max(np.abs(correction_cents))) if correction_cents else 0.0,
        "corrected_samples": int(output.shape[0]),
        "sample_rate": int(sr),
    }
    import json

    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump({"analysis": analysis.to_dict(), "statistics": stats}, fh, indent=2)

    logger.info("pitch_correction_complete", job_id=job_id, mode=mode, key=detected_key, scale=detected_scale)
    return PitchProcessResult(job_id, output_path, report_path, detected_key, detected_scale, stats)


def _smooth_correction(correction: np.ndarray, retune_speed: float) -> np.ndarray:
    if len(correction) < 3:
        return correction
    window = max(1, int(round(retune_speed * 18)))
    kernel = np.ones(window, dtype=np.float64) / window
    return np.convolve(correction, kernel, mode="same")


def _write_temp_bytes(audio: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, audio, sr, format="WAV", subtype="FLOAT")
    return buf.getvalue()
