"""AI instrument synthesis service backed by AudioCraft MusicGen."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import struct
import tempfile
import uuid

import numpy as np
import soundfile as sf
import structlog

from app.core.config import settings

logger = structlog.get_logger()

SUPPORTED_INSTRUMENTS = {
    "piano", "grand piano", "upright piano", "acoustic guitar", "electric guitar",
    "bass guitar", "synth bass", "orchestral strings", "brass", "woodwinds",
    "drums", "percussion", "pads", "cinematic textures", "ambient textures",
}


class InstrumentSynthesisError(RuntimeError):
    """Raised when synthesis cannot be completed."""


@dataclass(frozen=True)
class SynthesisResult:
    job_id: str
    wav_path: str | None
    midi_path: str
    metadata_path: str
    provenance_path: str
    metadata: dict


def synthesize_instrument(
    prompt: str,
    instrument: str,
    genre: str = "pop",
    tempo_bpm: int = 120,
    key: str = "C",
    duration_seconds: float = 12.0,
    stems: bool = False,
) -> SynthesisResult:
    instrument = instrument.strip().lower()
    if instrument not in SUPPORTED_INSTRUMENTS:
        raise InstrumentSynthesisError(f"Unsupported instrument: {instrument}")
    duration_seconds = float(np.clip(duration_seconds, 1.0, 180.0))
    tempo_bpm = int(np.clip(tempo_bpm, 40, 240))

    job_id = str(uuid.uuid4())
    out_dir = Path(tempfile.gettempdir()) / "rain_instrument_synthesis" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)

    midi_path = str(out_dir / f"{instrument.replace(' ', '_')}.mid")
    _write_midi(midi_path, instrument, key, tempo_bpm, duration_seconds)

    full_prompt = _compose_prompt(prompt, instrument, genre, tempo_bpm, key, stems)
    wav_path: str | None = None
    if settings.INSTRUMENT_SYNTHESIS_ENABLED:
        wav_path = str(out_dir / f"{instrument.replace(' ', '_')}.wav")
        _musicgen_to_wav(full_prompt, wav_path, duration_seconds)
    else:
        logger.info("instrument_synthesis_wav_disabled", job_id=job_id)

    metadata = {
        "job_id": job_id,
        "prompt": prompt,
        "expanded_prompt": full_prompt,
        "instrument": instrument,
        "genre": genre,
        "tempo_bpm": tempo_bpm,
        "key": key,
        "duration_seconds": duration_seconds,
        "outputs": {"wav": wav_path, "midi": midi_path},
    }
    metadata_path = str(out_dir / "metadata.json")
    provenance_path = str(out_dir / "provenance.json")
    with open(metadata_path, "w", encoding="utf-8") as fh:
        json.dump(metadata, fh, indent=2)
    with open(provenance_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "engine": "AudioCraft MusicGen",
                "model": settings.MUSICGEN_MODEL_NAME,
                "ai_generated": True,
                "input_prompt_hash": str(abs(hash(full_prompt))),
                "instrument": instrument,
            },
            fh,
            indent=2,
        )

    return SynthesisResult(job_id, wav_path, midi_path, metadata_path, provenance_path, metadata)


def _compose_prompt(prompt: str, instrument: str, genre: str, tempo_bpm: int, key: str, stems: bool) -> str:
    stem_text = "isolated dry stem, no full mix" if stems else "complete musical phrase"
    return (
        f"{prompt}. Instrument: {instrument}. Genre: {genre}. Tempo: {tempo_bpm} BPM. "
        f"Key: {key}. Render as {stem_text}, studio quality, clean transient detail."
    )


def _musicgen_to_wav(prompt: str, wav_path: str, duration_seconds: float) -> None:
    try:
        import torch
        from audiocraft.models import MusicGen
    except ImportError as exc:
        raise InstrumentSynthesisError(
            "AudioCraft is required for WAV synthesis. Install audiocraft and enable INSTRUMENT_SYNTHESIS_ENABLED."
        ) from exc

    model = MusicGen.get_pretrained(settings.MUSICGEN_MODEL_NAME)
    model.set_generation_params(duration=duration_seconds)
    with torch.no_grad():
        wav = model.generate([prompt], progress=False)[0].detach().cpu().numpy()
    if wav.ndim == 2:
        wav = wav.T
    sr = int(getattr(model.compression_model, "sample_rate", 32000))
    peak = float(np.max(np.abs(wav))) if wav.size else 0.0
    if peak > 0.98:
        wav = wav / peak * 0.98
    sf.write(wav_path, wav.astype(np.float32), sr, subtype="PCM_24")


def _write_midi(path: str, instrument: str, key: str, tempo_bpm: int, duration_seconds: float) -> None:
    ticks_per_quarter = 480
    tempo_us = int(60_000_000 / tempo_bpm)
    notes = _pattern_notes(instrument, key)
    note_len_ticks = ticks_per_quarter
    total_ticks = int((duration_seconds / 60.0) * tempo_bpm * ticks_per_quarter)

    events: list[tuple[int, bytes]] = [
        (0, b"\xff\x51\x03" + tempo_us.to_bytes(3, "big")),
        (0, b"\xc0" + bytes([_program_for_instrument(instrument)])),
    ]
    tick = 0
    idx = 0
    while tick < total_ticks:
        note = notes[idx % len(notes)]
        velocity = 92 if "drum" not in instrument and "percussion" not in instrument else 110
        events.append((tick, b"\x90" + bytes([note, velocity])))
        events.append((min(tick + note_len_ticks, total_ticks), b"\x80" + bytes([note, 0])))
        tick += note_len_ticks
        idx += 1
    events.append((total_ticks + 1, b"\xff\x2f\x00"))
    events.sort(key=lambda item: item[0])

    track = bytearray()
    last_tick = 0
    for tick, payload in events:
        track.extend(_varlen(max(0, tick - last_tick)))
        track.extend(payload)
        last_tick = tick

    with open(path, "wb") as fh:
        fh.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, ticks_per_quarter))
        fh.write(b"MTrk" + struct.pack(">I", len(track)) + bytes(track))


def _varlen(value: int) -> bytes:
    buffer = value & 0x7F
    value >>= 7
    out = []
    while value:
        out.insert(0, 0x80 | buffer)
        buffer = value & 0x7F
        value >>= 7
    out.insert(0, buffer)
    return bytes(out)


def _pattern_notes(instrument: str, key: str) -> list[int]:
    root_pc = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}.get(key.upper(), 0)
    octave = 36 if "bass" in instrument else 48 if "drum" in instrument or "percussion" in instrument else 60
    if "drum" in instrument:
        return [36, 38, 42, 36, 38, 46]
    return [octave + root_pc + interval for interval in (0, 4, 7, 9, 7, 4)]


def _program_for_instrument(instrument: str) -> int:
    if "guitar" in instrument:
        return 24 if "acoustic" in instrument else 27
    if "bass" in instrument:
        return 38
    if "string" in instrument:
        return 48
    if "brass" in instrument:
        return 61
    if "woodwind" in instrument:
        return 73
    if "pad" in instrument or "texture" in instrument:
        return 89
    return 0
