"""
6-Band Linkwitz-Riley 8th Order Multiband Compressor — RAIN V6 Production
Crossover frequencies: 40, 160, 600, 2500, 8000 Hz (5 crossovers → 6 bands)

Filter bank design:
- LP filter: 8th-order (two cascaded 4th-order Butterworth), zero-phase via sosfiltfilt
- HP band: computed as complement (residual - LP) → perfect reconstruction guaranteed
- Reconstruction error: < 1e-10 (floating-point floor)

Per-band dynamics:
- Peak-tracking envelope follower with independent attack/release IIR coefficients
- Hard-knee gain computer (standard mastering compressor curve)
- Stereo: sidechain from max(|L|, |R|) — coupled stereo, standard for mastering

Band names (must match ProcessingParams field suffixes):
  low / low_mid / mid / high_mid / high / air

Entry points:
  apply_6band_multiband(audio, params, sr) — main pipeline call
  test_lr8_unity(audio, sr) → float  — QA helper
"""

from __future__ import annotations

import numpy as np
from scipy import signal
from typing import List

BAND_NAMES: List[str] = ["low", "low_mid", "mid", "high_mid", "high", "air"]
CROSSOVERS: List[float] = [40.0, 160.0, 600.0, 2500.0, 8000.0]  # Hz


# ---------------------------------------------------------------------------
# Filter bank — complementary LP/HP with perfect reconstruction
# ---------------------------------------------------------------------------

def _design_lr8_lp_sos(freq: float, sr: int) -> np.ndarray:
    """8th-order LR LP = two cascaded 4th-order Butterworth, same cutoff."""
    nyq = sr / 2.0
    wn = float(np.clip(freq / nyq, 1e-6, 1.0 - 1e-6))
    sos4 = signal.butter(4, wn, btype="low", analog=False, output="sos")
    return np.vstack([sos4, sos4])  # cascade → 8th order


def split_6band(audio: np.ndarray, sr: int) -> List[np.ndarray]:
    """
    Split audio into 6 frequency bands with perfect reconstruction.

    Uses complementary HP = residual - LP at each stage so that
    sum(bands) == audio to floating-point precision (< 1e-10 error).

    Args:
        audio: (samples,) or (samples, channels) float64
        sr:    sample rate

    Returns:
        List of 6 arrays, each same shape as audio.
    """
    bands: List[np.ndarray] = []
    residual = audio.copy()

    for freq in CROSSOVERS:
        sos_lp = _design_lr8_lp_sos(freq, sr)
        low = signal.sosfiltfilt(sos_lp, residual, axis=0)
        high = residual - low          # complementary HP: perfect reconstruction
        bands.append(low)
        residual = high                # next stage acts on remaining high content

    bands.append(residual)            # air band: everything above 8 kHz
    return bands


# ---------------------------------------------------------------------------
# Envelope follower
# ---------------------------------------------------------------------------

def _time_to_coeff(time_ms: float, sr: int) -> float:
    """Convert attack/release time (ms) to per-sample IIR coefficient."""
    if time_ms <= 0.0:
        return 0.0
    return float(np.exp(-1.0 / (sr * time_ms * 1e-3)))


def _peak_envelope(x: np.ndarray, att: float, rel: float) -> np.ndarray:
    """
    Per-sample peak envelope follower on 1D signal.
    att, rel: IIR coefficients from _time_to_coeff (closer to 1 = slower).
    """
    env = np.empty_like(x)
    prev = 0.0
    for i in range(len(x)):
        level = abs(x[i])
        if level > prev:
            prev = att * prev + (1.0 - att) * level
        else:
            prev = rel * prev + (1.0 - rel) * level
        env[i] = prev
    return env


# ---------------------------------------------------------------------------
# Gain computer (hard-knee)
# ---------------------------------------------------------------------------

def _gain_computer(
    env_lin: np.ndarray, threshold_db: float, ratio: float
) -> np.ndarray:
    """
    Hard-knee gain computer in log domain (standard compressor law).
    Returns linear gain factor in (0, 1].

    Above threshold:
        input_db  = 20*log10(env_lin)
        output_db = threshold + (input_db - threshold) / ratio
        gain_db   = output_db - input_db  = (1 - 1/ratio) * (threshold - input_db)
    Below threshold: gain = 1.0 (unity)
    """
    env_db = 20.0 * np.log10(np.maximum(env_lin, 1e-12))
    over_db = np.maximum(env_db - threshold_db, 0.0)
    gain_db = -(1.0 - 1.0 / max(ratio, 1.0)) * over_db   # always <= 0
    gain_lin = 10.0 ** (gain_db / 20.0)
    return np.clip(gain_lin, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Per-band compressor
# ---------------------------------------------------------------------------

def _compress_band(
    band: np.ndarray,
    threshold_db: float,
    ratio: float,
    attack_ms: float,
    release_ms: float,
    sr: int,
) -> np.ndarray:
    """
    Apply mastering compressor to one frequency band.

    Stereo: coupled sidechain from max(|L|, |R|) — preserves image.
    Mono:   sidechain = |x|.

    Bypasses cleanly when ratio <= 1 or threshold >= 0 dBFS.
    """
    if ratio <= 1.0 or threshold_db >= 0.0:
        return band

    att = _time_to_coeff(attack_ms, sr)
    rel = _time_to_coeff(release_ms, sr)

    if band.ndim == 1:
        env = _peak_envelope(band, att, rel)
    else:
        # Coupled stereo: use peak across channels as sidechain
        sidechain = np.max(np.abs(band), axis=1)
        env = _peak_envelope(sidechain, att, rel)

    gain = _gain_computer(env, threshold_db, ratio)

    if band.ndim == 1:
        return band * gain
    else:
        return band * gain[:, np.newaxis]


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def apply_6band_multiband(
    audio: np.ndarray, params: object, sr: int = 48000
) -> np.ndarray:
    """
    6-band LR8 multiband compressor. Drop-in for Stage 10 of master_engine.

    Args:
        audio:  (samples, channels) or (samples,) float64
        params: ProcessingParams — reads mb_threshold_*, mb_ratio_*,
                mb_attack_*, mb_release_* for each band in BAND_NAMES.
                Falls back to sensible defaults via getattr if field missing.
        sr:     sample rate (Hz), default 48000

    Returns:
        Processed audio, same shape as input. Clipped to [-1, 1] before return.
    """
    bands = split_6band(audio, sr)
    processed: List[np.ndarray] = []

    for band_audio, name in zip(bands, BAND_NAMES):
        threshold = float(getattr(params, f"mb_threshold_{name}", -20.0))
        ratio = float(getattr(params, f"mb_ratio_{name}", 2.0))
        attack = float(getattr(params, f"mb_attack_{name}", 5.0))
        release = float(getattr(params, f"mb_release_{name}", 80.0))

        processed.append(
            _compress_band(band_audio, threshold, ratio, attack, release, sr)
        )

    output = np.sum(processed, axis=0)
    # Safety ceiling — limiter follows this stage and will handle loudness
    np.clip(output, -1.0, 1.0, out=output)
    return output


# ---------------------------------------------------------------------------
# QA helper
# ---------------------------------------------------------------------------

def test_lr8_unity(audio: np.ndarray, sr: int) -> float:
    """
    Returns max absolute reconstruction error across all samples.
    Passing threshold: < 1e-6 (typically < 1e-10 in practice).
    """
    bands = split_6band(audio, sr)
    recon = np.sum(bands, axis=0)
    return float(np.max(np.abs(audio - recon)))
