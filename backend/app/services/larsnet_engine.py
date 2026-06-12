"""LarsNet drum sub-separation adapter.

RAIN does not synthesize fake drum stems when LarsNet assets are missing. The
service loads a configured TorchScript or ONNX LarsNet artifact and otherwise
raises LarsNetUnavailable so callers can use the documented fallback hierarchy.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import structlog
import torch

from app.core.config import settings

logger = structlog.get_logger()

LARSNET_STEMS = ("kick", "snare", "tom", "cymbal", "overhead", "room")


class LarsNetUnavailable(RuntimeError):
    """Raised when a configured LarsNet model cannot be loaded or executed."""


@dataclass(frozen=True)
class LarsNetResult:
    stems: dict[str, np.ndarray]
    confidence_scores: dict[str, float]
    quality_metrics: dict[str, float]
    method: str
    device: str


_torch_model: torch.jit.ScriptModule | None = None


def _device() -> torch.device:
    requested = settings.LARSNET_DEVICE
    if requested.startswith("cuda") and not torch.cuda.is_available():
        logger.warning("larsnet_cuda_unavailable", fallback="cpu")
        requested = "cpu"
    return torch.device(requested)


def _load_torchscript(path: Path, device: torch.device):
    global _torch_model
    if _torch_model is None:
        _torch_model = torch.jit.load(str(path), map_location=device).eval()
        logger.info("larsnet_torchscript_loaded", path=str(path), device=str(device))
    return _torch_model


def separate_drums(drums: np.ndarray, sr: int) -> LarsNetResult:
    if not settings.LARSNET_ENABLED:
        raise LarsNetUnavailable("LarsNet disabled. Set LARSNET_ENABLED=true and LARSNET_MODEL_PATH.")

    model_path = Path(settings.LARSNET_MODEL_PATH)
    if not model_path.exists():
        raise LarsNetUnavailable(f"LarsNet model not found: {model_path}")
    if sr <= 0 or drums.size == 0:
        raise LarsNetUnavailable("Invalid drum audio for LarsNet separation")

    if model_path.suffix.lower() in {".pt", ".ts", ".torchscript"}:
        return _separate_torchscript(model_path, drums, sr)
    if model_path.suffix.lower() == ".onnx":
        return _separate_onnx(model_path, drums, sr)
    raise LarsNetUnavailable(f"Unsupported LarsNet model format: {model_path.suffix}")


def separate_with_fallback(
    drums: np.ndarray,
    sr: int,
    bsroformer_fallback: Callable[[np.ndarray, int], dict[str, np.ndarray]] | None,
    spectral_fallback: Callable[[np.ndarray, int], dict[str, np.ndarray]],
) -> LarsNetResult:
    try:
        return separate_drums(drums, sr)
    except LarsNetUnavailable as exc:
        logger.warning("larsnet_unavailable", reason=str(exc), fallback="bs_roformer")

    if bsroformer_fallback is not None:
        try:
            stems = bsroformer_fallback(drums, sr)
            normalized = _normalize_stem_names(stems, drums)
            return LarsNetResult(
                normalized,
                _confidence(normalized, drums),
                _quality(normalized, drums),
                "bs_roformer_drum_fallback",
                str(_device()),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("bs_roformer_drum_fallback_failed", error=str(exc), fallback="spectral")

    stems = spectral_fallback(drums, sr)
    return LarsNetResult(stems, _confidence(stems, drums), _quality(stems, drums), "spectral_drum_fallback", "cpu")


def _separate_torchscript(model_path: Path, drums: np.ndarray, sr: int) -> LarsNetResult:
    device = _device()
    model = _load_torchscript(model_path, device)
    audio = drums.astype(np.float32)
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
    tensor = torch.from_numpy(audio[None, :, :]).to(device)
    with torch.no_grad():
        output = model(tensor)
    if isinstance(output, dict):
        stems = {name: _to_numpy(output[name], drums) for name in LARSNET_STEMS if name in output}
    else:
        arr = output.detach().cpu().numpy()[0]
        stems = {name: arr[i] for i, name in enumerate(LARSNET_STEMS[: arr.shape[0]])}
    stems = _normalize_stem_names(stems, drums)
    return LarsNetResult(stems, _confidence(stems, drums), _quality(stems, drums), "larsnet_torchscript", str(device))


def _separate_onnx(model_path: Path, drums: np.ndarray, sr: int) -> LarsNetResult:
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise LarsNetUnavailable("onnxruntime is required for ONNX LarsNet inference") from exc
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] if settings.LARSNET_DEVICE.startswith("cuda") else ["CPUExecutionProvider"]
    session = ort.InferenceSession(str(model_path), providers=providers)
    input_name = session.get_inputs()[0].name
    audio = drums.astype(np.float32)
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
    out = session.run(None, {input_name: audio[None, :, :]})[0][0]
    stems = {name: out[i] for i, name in enumerate(LARSNET_STEMS[: out.shape[0]])}
    stems = _normalize_stem_names(stems, drums)
    return LarsNetResult(stems, _confidence(stems, drums), _quality(stems, drums), "larsnet_onnx", ",".join(session.get_providers()))


def _to_numpy(value, reference: np.ndarray) -> np.ndarray:
    arr = value.detach().cpu().numpy() if hasattr(value, "detach") else np.asarray(value)
    if arr.ndim == 3:
        arr = arr[0]
    return _match_shape(arr.astype(np.float32), reference)


def _normalize_stem_names(stems: dict[str, np.ndarray], reference: np.ndarray) -> dict[str, np.ndarray]:
    aliases = {"hats": "cymbal", "percussion": "overhead", "toms": "tom"}
    normalized: dict[str, np.ndarray] = {}
    for name, audio in stems.items():
        canonical = aliases.get(name.lower(), name.lower())
        if canonical in LARSNET_STEMS:
            normalized[canonical] = _match_shape(audio, reference)
    residual = reference.astype(np.float32) - sum(normalized.values(), np.zeros_like(reference, dtype=np.float32))
    for stem in LARSNET_STEMS:
        normalized.setdefault(stem, residual / max(1, len(LARSNET_STEMS)))
    return normalized


def _match_shape(audio: np.ndarray, reference: np.ndarray) -> np.ndarray:
    arr = audio
    if arr.ndim == 1:
        arr = np.tile(arr[None, :], (reference.shape[0], 1))
    if arr.shape[0] != reference.shape[0] and arr.shape[-1] == reference.shape[0]:
        arr = arr.T
    out = np.zeros_like(reference, dtype=np.float32)
    n = min(out.shape[1], arr.shape[1])
    c = min(out.shape[0], arr.shape[0])
    out[:c, :n] = arr[:c, :n]
    return out


def _confidence(stems: dict[str, np.ndarray], source: np.ndarray) -> dict[str, float]:
    source_energy = float(np.mean(source.astype(np.float64) ** 2)) + 1e-12
    scores = {}
    for name, audio in stems.items():
        energy = float(np.mean(audio.astype(np.float64) ** 2))
        scores[name] = float(np.clip(energy / source_energy, 0.0, 1.0))
    return scores


def _quality(stems: dict[str, np.ndarray], source: np.ndarray) -> dict[str, float]:
    reconstruction = sum(stems.values(), np.zeros_like(source, dtype=np.float32))
    residual = source.astype(np.float32) - reconstruction
    source_rms = float(np.sqrt(np.mean(source.astype(np.float64) ** 2))) + 1e-12
    residual_rms = float(np.sqrt(np.mean(residual.astype(np.float64) ** 2)))
    return {
        "reconstruction_error_ratio": residual_rms / source_rms,
        "stem_count": float(len(stems)),
        "peak": float(max(np.max(np.abs(stem)) for stem in stems.values())) if stems else 0.0,
    }
