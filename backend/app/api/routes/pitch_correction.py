"""Pitch correction API routes."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.pitch_correction_service import (
    PitchCorrectionError,
    analyze_pitch,
    process_pitch,
)

router = APIRouter(prefix="/pitch-correction", tags=["pitch correction"])

_jobs: dict[str, dict[str, Any]] = {}


class PitchJobResponse(BaseModel):
    job_id: str
    status: str
    detected_key: str
    detected_scale: str
    statistics: dict[str, float | int | str]
    corrected_wav_url: str
    report_url: str


@router.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> dict[str, Any]:
    data = await file.read()
    try:
        return analyze_pitch(data).to_dict()
    except PitchCorrectionError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E810", "message": str(exc)}) from exc


@router.post("/process", response_model=PitchJobResponse)
async def process(
    file: UploadFile = File(...),
    mode: Literal["transparent", "natural", "aggressive"] = Form("natural"),
    strength: float | None = Form(None),
    retune_speed: float | None = Form(None),
    humanization: float | None = Form(None),
    key: str | None = Form(None),
    scale: str | None = Form(None),
) -> PitchJobResponse:
    data = await file.read()
    try:
        result = process_pitch(data, mode, strength, retune_speed, humanization, key, scale)
    except PitchCorrectionError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E811", "message": str(exc)}) from exc

    _jobs[result.job_id] = {"status": "complete", **result.__dict__}
    return PitchJobResponse(
        job_id=result.job_id,
        status="complete",
        detected_key=result.detected_key,
        detected_scale=result.detected_scale,
        statistics=result.statistics,
        corrected_wav_url=f"/api/v1/pitch-correction/job/{result.job_id}/download",
        report_url=f"/api/v1/pitch-correction/job/{result.job_id}/report",
    )


@router.post("/preview", response_model=PitchJobResponse)
async def preview(
    file: UploadFile = File(...),
    mode: Literal["transparent", "natural", "aggressive"] = Form("natural"),
    strength: float | None = Form(None),
    retune_speed: float | None = Form(None),
    humanization: float | None = Form(None),
    key: str | None = Form(None),
    scale: str | None = Form(None),
    preview_seconds: float = Form(20.0),
) -> PitchJobResponse:
    data = await file.read()
    try:
        result = process_pitch(
            data,
            mode,
            strength,
            retune_speed,
            humanization,
            key,
            scale,
            preview_seconds=max(1.0, min(preview_seconds, 45.0)),
        )
    except PitchCorrectionError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E812", "message": str(exc)}) from exc
    _jobs[result.job_id] = {"status": "complete", **result.__dict__}
    return PitchJobResponse(
        job_id=result.job_id,
        status="complete",
        detected_key=result.detected_key,
        detected_scale=result.detected_scale,
        statistics=result.statistics,
        corrected_wav_url=f"/api/v1/pitch-correction/job/{result.job_id}/download",
        report_url=f"/api/v1/pitch-correction/job/{result.job_id}/report",
    )


@router.get("/job/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "RAIN-E813", "message": "Pitch correction job not found"})
    return {
        "job_id": job_id,
        "status": job["status"],
        "detected_key": job["detected_key"],
        "detected_scale": job["detected_scale"],
        "statistics": job["statistics"],
        "corrected_wav_url": f"/api/v1/pitch-correction/job/{job_id}/download",
        "report_url": f"/api/v1/pitch-correction/job/{job_id}/report",
    }


@router.get("/job/{job_id}/download")
async def download(job_id: str) -> FileResponse:
    job = _jobs.get(job_id)
    if not job or not Path(job["output_path"]).exists():
        raise HTTPException(status_code=404, detail={"code": "RAIN-E814", "message": "Corrected WAV not found"})
    return FileResponse(job["output_path"], media_type="audio/wav", filename=f"{job_id}_corrected.wav")


@router.get("/job/{job_id}/report")
async def report(job_id: str) -> FileResponse:
    job = _jobs.get(job_id)
    if not job or not Path(job["report_path"]).exists():
        raise HTTPException(status_code=404, detail={"code": "RAIN-E815", "message": "Correction report not found"})
    return FileResponse(job["report_path"], media_type="application/json", filename=f"{job_id}_report.json")
