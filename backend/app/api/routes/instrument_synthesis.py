"""Instrument synthesis API routes."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.instrument_synthesis_service import (
    InstrumentSynthesisError,
    SUPPORTED_INSTRUMENTS,
    synthesize_instrument,
)

router = APIRouter(prefix="/instrument-synthesis", tags=["instrument synthesis"])

_jobs: dict[str, dict[str, Any]] = {}


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=3)
    instrument: str
    genre: str = "pop"
    tempo_bpm: int = Field(120, ge=40, le=240)
    key: str = "C"
    duration_seconds: float = Field(12.0, ge=1.0, le=180.0)


def _response(result) -> dict[str, Any]:
    _jobs[result.job_id] = result.__dict__
    return {
        "job_id": result.job_id,
        "status": "complete" if result.wav_path else "midi_complete_wav_disabled",
        "wav_url": f"/api/v1/instrument-synthesis/job/{result.job_id}/wav" if result.wav_path else None,
        "midi_url": f"/api/v1/instrument-synthesis/job/{result.job_id}/midi",
        "metadata_url": f"/api/v1/instrument-synthesis/job/{result.job_id}/metadata",
        "provenance_url": f"/api/v1/instrument-synthesis/job/{result.job_id}/provenance",
        "metadata": result.metadata,
    }


@router.get("/instruments")
async def instruments() -> dict[str, list[str]]:
    return {"supported_instruments": sorted(SUPPORTED_INSTRUMENTS)}


@router.post("/generate")
async def generate(req: GenerateRequest) -> dict[str, Any]:
    try:
        return _response(synthesize_instrument(**req.model_dump(), stems=False))
    except InstrumentSynthesisError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E830", "message": str(exc)}) from exc


@router.post("/preview")
async def preview(req: GenerateRequest) -> dict[str, Any]:
    data = req.model_dump()
    data["duration_seconds"] = min(float(data["duration_seconds"]), 15.0)
    try:
        return _response(synthesize_instrument(**data, stems=False))
    except InstrumentSynthesisError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E831", "message": str(exc)}) from exc


@router.post("/stems")
async def stems(req: GenerateRequest) -> dict[str, Any]:
    try:
        return _response(synthesize_instrument(**req.model_dump(), stems=True))
    except InstrumentSynthesisError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E832", "message": str(exc)}) from exc


@router.post("/midi")
async def midi(req: GenerateRequest) -> dict[str, Any]:
    data = req.model_dump()
    try:
        return _response(synthesize_instrument(**data, stems=False))
    except InstrumentSynthesisError as exc:
        raise HTTPException(status_code=400, detail={"code": "RAIN-E833", "message": str(exc)}) from exc


def _path(job_id: str, key: str) -> str:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "RAIN-E834", "message": "Synthesis job not found"})
    path = job.get(key)
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail={"code": "RAIN-E835", "message": f"{key} not found"})
    return path


@router.get("/job/{job_id}/wav")
async def wav(job_id: str) -> FileResponse:
    return FileResponse(_path(job_id, "wav_path"), media_type="audio/wav", filename=f"{job_id}.wav")


@router.get("/job/{job_id}/midi")
async def midi_file(job_id: str) -> FileResponse:
    return FileResponse(_path(job_id, "midi_path"), media_type="audio/midi", filename=f"{job_id}.mid")


@router.get("/job/{job_id}/metadata")
async def metadata(job_id: str) -> FileResponse:
    return FileResponse(_path(job_id, "metadata_path"), media_type="application/json", filename=f"{job_id}_metadata.json")


@router.get("/job/{job_id}/provenance")
async def provenance(job_id: str) -> FileResponse:
    return FileResponse(_path(job_id, "provenance_path"), media_type="application/json", filename=f"{job_id}_provenance.json")
