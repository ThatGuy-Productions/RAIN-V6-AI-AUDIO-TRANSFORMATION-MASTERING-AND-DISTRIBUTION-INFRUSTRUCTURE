"""RainNet training API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.rainnet_training import (
    RainNetTrainingError,
    create_training_job,
    evaluate_checkpoint,
    export_job,
    generate_splits,
    get_job,
)

router = APIRouter(prefix="/rainnet", tags=["rainnet"])


class TrainRequest(BaseModel):
    manifest_path: str
    epochs: int = Field(10, ge=1, le=500)
    batch_size: int = Field(8, ge=1, le=256)
    lr: float = Field(1e-4, gt=0.0)
    device: str = "cuda"
    resume_checkpoint: str | None = None
    mixed_precision: bool = True


class EvaluateRequest(BaseModel):
    checkpoint_path: str
    manifest_path: str
    device: str = "cpu"


class ExportRequest(BaseModel):
    checkpoint_path: str
    output_path: str
    export_format: str = "onnx"


@router.post("/train")
async def train(req: TrainRequest) -> dict:
    try:
        job = create_training_job(**req.model_dump())
        return job.__dict__
    except RainNetTrainingError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E850", "message": str(exc)}) from exc


@router.post("/evaluate")
async def evaluate(req: EvaluateRequest) -> dict:
    try:
        return evaluate_checkpoint(**req.model_dump())
    except RainNetTrainingError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E851", "message": str(exc)}) from exc


@router.post("/export")
async def export(req: ExportRequest) -> dict:
    try:
        path = export_job(**req.model_dump())
        return {"status": "complete", "output_path": path}
    except RainNetTrainingError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E852", "message": str(exc)}) from exc


@router.post("/split")
async def split(req: dict) -> dict:
    try:
        return generate_splits(req["manifest_path"], req["output_dir"], float(req.get("validation_ratio", 0.1)))
    except (KeyError, RainNetTrainingError) as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E853", "message": str(exc)}) from exc


@router.get("/jobs/{job_id}")
async def job(job_id: str) -> dict:
    result = get_job(job_id)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "RAIN-E854", "message": "RainNet job not found"})
    return result.__dict__
