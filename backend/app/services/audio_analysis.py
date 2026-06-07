"""Audio analysis utilities: mel spectrogram extraction, duration, sample rate."""
from __future__ import annotations
from io import BytesIO
from typing import Tuple
import numpy as np
import structlog
import asyncio
from concurrent.futures import ProcessPoolExecutor
from functools import partial

logger = structlog.get_logger()

# Global process pool to avoid locking the Python GIL during heavy audio analysis
# on the API request path.
_process_pool = ProcessPoolExecutor(max_workers=2)

def extract_mel_spectrogram_sync(
    audio_data: bytes,
    sr_target: int = 48000,
    n_mels: int = 128,
    n_frames: int = 128,
    hop_length: int = 512,
    n_fft: int = 2048,
) -> Tuple[np.ndarray, float, float]:
    """
    Returns (mel_spectrogram, duration_seconds, sample_rate).
    mel_spectrogram shape: [128, 128] float32, values in [0, 1].
    """
    import librosa
    import soundfile as sf

    audio, sr = sf.read(BytesIO(audio_data), dtype="float32", always_2d=False)
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)  # downmix to mono for analysis

    if sr != sr_target:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=sr_target)
        sr = sr_target

    duration = float(len(audio) / sr)

    target_len = n_frames * hop_length
    if len(audio) < target_len:
        audio = np.pad(audio, (0, target_len - len(audio)))
    else:
        start = max(0, (len(audio) - target_len) // 2)
        audio = audio[start : start + target_len]

    mel = librosa.feature.melspectrogram(
        y=audio, sr=sr, n_mels=n_mels, n_fft=n_fft, hop_length=hop_length
    )
    mel_db = librosa.power_to_db(mel, ref=np.max)
    mel_min, mel_max = mel_db.min(), mel_db.max()
    mel_norm = (mel_db - mel_min) / (mel_max - mel_min + 1e-8)

    return mel_norm.astype(np.float32)[:, :n_frames], duration, float(sr)


async def extract_mel_spectrogram(
    audio_data: bytes,
    sr_target: int = 48000,
    n_mels: int = 128,
    n_frames: int = 128,
    hop_length: int = 512,
    n_fft: int = 2048,
) -> Tuple[np.ndarray, float, float]:
    """Asynchronous wrapper for mel spectrogram extraction using ProcessPoolExecutor."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _process_pool,
        partial(
            extract_mel_spectrogram_sync,
            audio_data,
            sr_target,
            n_mels,
            n_frames,
            hop_length,
            n_fft
        )
    )


def measure_lufs_true_peak_sync(audio_data: bytes) -> tuple[float, float]:
    """Synchronous implementation of LUFS/Peak measurement."""
    import soundfile as sf
    import pyloudnorm as pyln
    import numpy as np

    audio, sr = sf.read(BytesIO(audio_data), dtype="float64", always_2d=True)
    meter = pyln.Meter(sr)  # BS.1770-4
    loudness = meter.integrated_loudness(audio)
    # True peak: max absolute value across all samples, converted to dBFS
    true_peak_linear = float(np.max(np.abs(audio)))
    true_peak_dbtp = 20.0 * np.log10(true_peak_linear) if true_peak_linear > 0 else -120.0
    return float(loudness), float(true_peak_dbtp)


async def measure_lufs_true_peak(audio_data: bytes) -> tuple[float, float]:
    """
    Measure integrated LUFS and true peak from raw audio bytes.
    Offloaded to a ProcessPoolExecutor to avoid blocking the API event loop.
    Returns (integrated_lufs, true_peak_dbtp).
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        _process_pool, 
        partial(measure_lufs_true_peak_sync, audio_data)
    )
