"""Production RainNet retraining orchestration."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Any
import json
import time
import uuid

import structlog

from app.core.config import settings

logger = structlog.get_logger()


class RainNetTrainingError(RuntimeError):
    """Raised when RainNet training cannot proceed."""


@dataclass
class RainNetJob:
    job_id: str
    status: str
    progress: float
    output_dir: str
    metrics: dict[str, Any]
    error: str | None = None


_jobs: dict[str, RainNetJob] = {}


def create_training_job(
    manifest_path: str,
    epochs: int = 10,
    batch_size: int = 8,
    lr: float = 1e-4,
    device: str = "cuda",
    resume_checkpoint: str | None = None,
    mixed_precision: bool = True,
) -> RainNetJob:
    if not settings.RAINNET_TRAINING_ENABLED:
        raise RainNetTrainingError("RainNet training disabled. Set RAINNET_TRAINING_ENABLED=true on a training worker.")
    manifest = Path(manifest_path)
    validate_manifest(manifest)
    job_id = str(uuid.uuid4())
    output_dir = Path(settings.RAINNET_TRAINING_OUTPUT_DIR) / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    job = RainNetJob(job_id, "queued", 0.0, str(output_dir), {})
    _jobs[job_id] = job
    thread = Thread(
        target=_run_training,
        args=(job, str(manifest), epochs, batch_size, lr, device, resume_checkpoint, mixed_precision),
        daemon=True,
    )
    thread.start()
    return job


def validate_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RainNetTrainingError(f"Manifest not found: {path}")
    count = 0
    missing_audio: list[str] = []
    with open(path, encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RainNetTrainingError(f"Invalid JSON at manifest line {line_no}: {exc}") from exc
            audio_path = Path(sample.get("audio_path", ""))
            if not audio_path.exists():
                missing_audio.append(str(audio_path))
            if "target_params" not in sample:
                raise RainNetTrainingError(f"target_params missing at manifest line {line_no}")
            count += 1
    if count < 2:
        raise RainNetTrainingError("RainNet training requires at least two samples")
    if missing_audio:
        raise RainNetTrainingError(f"Missing audio files: {missing_audio[:5]}")
    return {"samples": count}


def generate_splits(manifest_path: str, output_dir: str, validation_ratio: float = 0.1) -> dict[str, str]:
    manifest = Path(manifest_path)
    validate_manifest(manifest)
    lines = [line for line in manifest.read_text(encoding="utf-8").splitlines() if line.strip()]
    val_count = max(1, int(len(lines) * validation_ratio))
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    train_path = out / "train.jsonl"
    val_path = out / "validation.jsonl"
    train_path.write_text("\n".join(lines[:-val_count]) + "\n", encoding="utf-8")
    val_path.write_text("\n".join(lines[-val_count:]) + "\n", encoding="utf-8")
    return {"train_manifest": str(train_path), "validation_manifest": str(val_path)}


def export_job(checkpoint_path: str, output_path: str, export_format: str = "onnx") -> str:
    checkpoint = Path(checkpoint_path)
    if not checkpoint.exists():
        raise RainNetTrainingError(f"Checkpoint not found: {checkpoint}")
    export_format = export_format.lower()
    if export_format == "onnx":
        from ml.rainnet.export import export_onnx
        return export_onnx(str(checkpoint), output_path)
    if export_format == "torchscript":
        import torch
        from ml.rainnet.model import RainNetV2
        model = RainNetV2()
        state = torch.load(str(checkpoint), map_location="cpu")
        model.load_state_dict(state["model_state_dict"])
        model.eval()
        scripted = torch.jit.script(model)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        scripted.save(output_path)
        return output_path
    raise RainNetTrainingError(f"Unsupported export format: {export_format}")


def evaluate_checkpoint(checkpoint_path: str, manifest_path: str, device: str = "cpu") -> dict[str, float]:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader
    from ml.rainnet.dataset import RainNetDataset
    from ml.rainnet.model import RainNetV2

    validate_manifest(Path(manifest_path))
    dataset = RainNetDataset(manifest_path)
    loader = DataLoader(dataset, batch_size=8, shuffle=False, num_workers=0)
    model = RainNetV2().to(device)
    state = torch.load(checkpoint_path, map_location=device)
    model.load_state_dict(state["model_state_dict"])
    model.eval()
    criterion = nn.MSELoss()
    loss = 0.0
    mae = 0.0
    with torch.no_grad():
        for batch in loader:
            preds = model(
                batch["mel"].to(device),
                batch["artist_vec"].to(device),
                batch["genre_id"].to(device),
                batch["platform_id"].to(device),
                batch["simple_mode"].to(device),
            )
            targets = batch["target_params"].to(device)
            loss += float(criterion(preds, targets).item())
            mae += float((preds - targets).abs().mean().item())
    n = max(1, len(loader))
    return {"loss": loss / n, "accuracy": max(0.0, 1.0 - mae / 10.0), "validation_score": 1.0 / (1.0 + mae), "mastering_prediction_quality": max(0.0, 100.0 - mae * 10.0)}


def get_job(job_id: str) -> RainNetJob | None:
    return _jobs.get(job_id)


def _run_training(job: RainNetJob, manifest_path: str, epochs: int, batch_size: int, lr: float, device: str, resume_checkpoint: str | None, mixed_precision: bool) -> None:
    try:
        import torch
        import torch.nn as nn
        from torch.cuda.amp import GradScaler, autocast
        from torch.optim import AdamW
        from torch.optim.lr_scheduler import CosineAnnealingLR
        from torch.utils.data import DataLoader, random_split
        from ml.rainnet.dataset import RainNetDataset
        from ml.rainnet.model import RainNetV2

        if device.startswith("cuda") and not torch.cuda.is_available():
            device = "cpu"
        job.status = "running"
        dataset = RainNetDataset(manifest_path)
        val_size = max(1, len(dataset) // 10)
        train_ds, val_ds = random_split(dataset, [len(dataset) - val_size, val_size])
        train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
        val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
        model = RainNetV2().to(device)
        optimizer = AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
        start_epoch = 1
        if resume_checkpoint:
            state = torch.load(resume_checkpoint, map_location=device)
            model.load_state_dict(state["model_state_dict"])
            optimizer.load_state_dict(state["optimizer_state_dict"])
            start_epoch = int(state.get("epoch", 0)) + 1
        scheduler = CosineAnnealingLR(optimizer, T_max=max(epochs, 1))
        criterion = nn.MSELoss()
        scaler = GradScaler(enabled=mixed_precision and device.startswith("cuda"))
        for epoch in range(start_epoch, epochs + 1):
            model.train()
            total_loss = 0.0
            for batch in train_loader:
                optimizer.zero_grad()
                with autocast(enabled=mixed_precision and device.startswith("cuda")):
                    preds = model(
                        batch["mel"].to(device),
                        batch["artist_vec"].to(device),
                        batch["genre_id"].to(device),
                        batch["platform_id"].to(device),
                        batch["simple_mode"].to(device),
                    )
                    loss = criterion(preds, batch["target_params"].to(device))
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
                total_loss += float(loss.item())
            scheduler.step()
            val_mae = 0.0
            model.eval()
            with torch.no_grad():
                for batch in val_loader:
                    preds = model(
                        batch["mel"].to(device),
                        batch["artist_vec"].to(device),
                        batch["genre_id"].to(device),
                        batch["platform_id"].to(device),
                        batch["simple_mode"].to(device),
                    )
                    val_mae += float((preds - batch["target_params"].to(device)).abs().mean().item())
            ckpt = Path(job.output_dir) / f"rainnet_v2_epoch_{epoch}.pt"
            torch.save({"epoch": epoch, "model_state_dict": model.state_dict(), "optimizer_state_dict": optimizer.state_dict(), "created_at": time.time()}, ckpt)
            job.progress = epoch / max(epochs, 1)
            job.metrics = {
                "loss": total_loss / max(1, len(train_loader)),
                "validation_score": 1.0 / (1.0 + val_mae / max(1, len(val_loader))),
                "checkpoint": str(ckpt),
            }
        job.status = "complete"
    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.error = str(exc)
        logger.exception("rainnet_training_failed", job_id=job.job_id, error=str(exc))
