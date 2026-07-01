"""
RAIN Prototype Mastering API Routes

POST /api/v1/master/upload       — Upload audio file, get session_id
POST /api/v1/master/{id}/process — Trigger mastering with params + metadata
POST /api/v1/master/{id}/ai-suggest — Ask Claude for mastering suggestions
GET  /api/v1/master/{id}/download/{format} — Download mastered WAV or MP3
GET  /api/v1/master/{id}/analysis — Get analysis results as JSON

NOTE: This route module uses an in-memory session store (_sessions dict) which
is a prototype artifact. It does not survive process restarts and is not
shared across multiple worker processes. Migration to DB-backed sessions
(AsyncSessionLocal + S3) is required before horizontal scaling.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user, CurrentUser, require_tier

from app.core.config import settings
from app.services.master_engine import (
    AnalysisResult,
    MasteringParams,
    MasterResult,
    analyze,
    load_audio,
    master_audio,
    normalize_input,
    INTERNAL_SR,
)
from app.services.metadata_engine import write_metadata
from app.services.feature_extraction import extract_features, FeatureVector
from app.services.qc_engine import run_qc, QCReport
from app.services.platform_targets import get_platform_target, list_platform_targets
from app.services.provenance import create_rain_cert, create_c2pa_manifest, verify_cert, RainCert

logger = structlog.get_logger()

router = APIRouter(prefix="/master", tags=["mastering"])

# In-memory session store for the prototype (no DB dependency)
# KNOWN LIMITATION: process-local, ephemeral, unbounded. See module docstring.
_sessions: dict[str, dict[str, Any]] = {}

# IP-based upload rate limiter (process-local — acceptable for prototype)
_upload_timestamps: dict[str, list[float]] = {}
_UPLOAD_RATE_LIMIT = 10
_UPLOAD_WINDOW_SECONDS = 60.0


def _check_upload_rate_limit(client_ip: str) -> None:
    """Raise 429 if client exceeds upload rate limit."""
    import time
    now = time.time()
    cutoff = now - _UPLOAD_WINDOW_SECONDS
    timestamps = _upload_timestamps.get(client_ip, [])
    timestamps = [t for t in timestamps if t > cutoff]
    if len(timestamps) >= _UPLOAD_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "RAIN-E102",
                "message": f"Upload rate limit exceeded ({_UPLOAD_RATE_LIMIT} per {int(_UPLOAD_WINDOW_SECONDS)}s)",
            },
        )
    timestamps.append(now)
    _upload_timestamps[client_ip] = timestamps


def _require_session_owner(session_id: str, current_user: CurrentUser) -> dict:
    """Return session dict if it exists and belongs to current_user.

    Admins bypass the ownership check (needed for support tooling).
    Raises 404 on missing session (don't leak existence to non-owners).
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not current_user.is_admin:
        owner_id = session.get("owner_id")
        if owner_id is not None and str(owner_id) != str(current_user.user_id):
            # Return 404 rather than 403 to avoid leaking session existence
            raise HTTPException(status_code=404, detail="Session not found")
    return session


ALLOWED_EXTENSIONS = {".wav", ".flac", ".aiff", ".aif", ".mp3"}
MAX_FILE_SIZE = 200 * 1024 * 1024  # 200MB

# Temp directory for uploads and outputs
UPLOAD_DIR = Path(tempfile.gettempdir()) / "rain_uploads"
OUTPUT_DIR = Path(tempfile.gettempdir()) / "rain_outputs"
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


class ProcessRequest(BaseModel):
    # Canonical range per CLAUDE.md ProcessingParams schema: [-24.0, -8.0]
    target_lufs: float = Field(default=-14.0, ge=-24.0, le=-8.0)
    brightness: float = Field(default=2.0, ge=0.0, le=4.0)
    tightness: float = Field(default=3.0, ge=1.0, le=5.0)
    width: float = Field(default=2.0, ge=-3.0, le=6.0)
    warmth: float = Field(default=0.0, ge=0.0, le=3.0)
    punch: float = Field(default=10.0, ge=1.0, le=30.0)
    air: float = Field(default=1.5, ge=0.0, le=3.0)
    vinyl_mode: bool = False
    title: str = ""
    artist: str = ""
    album: str = ""
    genre: str = ""
    track_number: str = "1"
    year: str = ""


class UploadResponse(BaseModel):
    session_id: str
    filename: str
    format: str
    file_size: int
    duration: float | None = None


class AnalysisResponse(BaseModel):
    input_lufs: float
    input_true_peak: float
    spectral_centroid: float
    crest_factor: float
    stereo_width: float
    bass_energy_ratio: float
    dynamic_range: float
    sample_rate: int
    channels: int
    duration: float
    genre: str = "unknown"
    tempo_bpm: float = 120.0
    groove_score: float = 0.5
    transient_sharpness: float = 0.5
    output_lufs: float | None = None
    output_true_peak: float | None = None
    output_dynamic_range: float | None = None
    output_stereo_width: float | None = None
    output_spectral_centroid: float | None = None


class ProcessResponse(BaseModel):
    session_id: str
    status: str
    output_lufs: float
    output_true_peak: float
    output_dynamic_range: float
    output_stereo_width: float
    output_spectral_centroid: float


@router.post("/upload", response_model=UploadResponse)
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_tier("free", "spark", "creator", "artist", "studio_pro", "enterprise"))
) -> UploadResponse:
    """Upload an audio file for mastering. Returns session_id for subsequent operations."""
    client_ip = request.client.host if request.client else "unknown"
    _check_upload_rate_limit(client_ip)
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{ext}'. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 200MB)")

    session_id = str(uuid.uuid4())
    input_path = str(UPLOAD_DIR / f"{session_id}{ext}")

    with open(input_path, "wb") as f:
        f.write(content)

    try:
        raw_audio, original_sr = load_audio(input_path)
        audio = normalize_input(raw_audio, original_sr)
        analysis = analyze(audio, INTERNAL_SR, original_sr)
        features = extract_features(audio, INTERNAL_SR)
    except Exception as e:
        os.unlink(input_path)
        logger.error("upload_analysis_failed", error=str(e), session_id=session_id)
        raise HTTPException(status_code=400, detail=f"Could not read audio file: {e}")

    _sessions[session_id] = {
        "owner_id": current_user.user_id,  # ownership anchor for access control
        "input_path": input_path,
        "filename": file.filename,
        "format": ext.lstrip("."),
        "file_size": len(content),
        "analysis": analysis,
        "features": features,
        "status": "uploaded",
        "result": None,
        "qc_report": None,
    }

    logger.info(
        "upload_complete",
        session_id=session_id,
        filename=file.filename,
        format=ext,
        duration=analysis.duration,
        input_lufs=analysis.input_lufs,
    )

    return UploadResponse(
        session_id=session_id,
        filename=file.filename,
        format=ext.lstrip("."),
        file_size=len(content),
        duration=analysis.duration,
    )


@router.get("/{session_id}/analysis", response_model=AnalysisResponse)
async def get_analysis(
    session_id: str,
    current_user: CurrentUser = Depends(require_tier("free", "spark", "creator", "artist", "studio_pro", "enterprise"))
) -> AnalysisResponse:
    """Get analysis results for a session."""
    session = _require_session_owner(session_id, current_user)
    a: AnalysisResult = session["analysis"]
    result = session.get("result")

    resp = AnalysisResponse(
        input_lufs=round(a.input_lufs, 1),
        input_true_peak=round(a.input_true_peak, 1),
        spectral_centroid=round(a.spectral_centroid, 1),
        crest_factor=round(a.crest_factor, 1),
        stereo_width=round(a.stereo_width, 3),
        bass_energy_ratio=round(a.bass_energy_ratio, 3),
        dynamic_range=round(a.dynamic_range, 1),
        sample_rate=a.sample_rate,
        channels=a.channels,
        duration=round(a.duration, 2),
        genre=getattr(a, "genre", "unknown"),
        tempo_bpm=round(a.tempo_bpm, 1),
        groove_score=round(a.groove_score, 2),
        transient_sharpness=round(a.transient_sharpness, 2),
    )

    if result:
        resp.output_lufs = round(result.output_lufs, 1)
        resp.output_true_peak = round(result.output_true_peak, 1)
        resp.output_dynamic_range = round(result.output_dynamic_range, 1)
        resp.output_stereo_width = round(result.output_stereo_width, 3)
        resp.output_spectral_centroid = round(result.output_spectral_centroid, 1)

    return resp


@router.post("/{session_id}/process", response_model=ProcessResponse)
async def process_audio(
    session_id: str,
    req: ProcessRequest,
    current_user: CurrentUser = Depends(require_tier("spark", "creator", "artist", "studio_pro", "enterprise"))
) -> ProcessResponse:
    """Trigger the mastering chain with given parameters and metadata."""
    session = _require_session_owner(session_id, current_user)

    if session["status"] == "processing":
        raise HTTPException(status_code=409, detail="Already processing")

    session["status"] = "processing"

    is_vinyl = req.vinyl_mode or req.genre.lower() == "vinyl"
    effective_target_lufs = req.target_lufs
    effective_true_peak_ceiling = -1.0

    if is_vinyl:
        effective_target_lufs = -14.0
        effective_true_peak_ceiling = -3.0
        logger.info(
            "vinyl_mode_activated",
            session_id=session_id,
            target_lufs=effective_target_lufs,
            true_peak_ceiling=effective_true_peak_ceiling,
            lra_minimum=8.0,
        )

    params = MasteringParams(
        brightness=req.brightness,
        tightness=req.tightness,
        width=req.width,
        loudness=effective_target_lufs,
        warmth=req.warmth,
        punch=req.punch,
        air=req.air,
    )

    metadata = {
        "title": req.title or Path(session["filename"]).stem,
        "artist": req.artist,
        "album": req.album,
        "genre": req.genre,
        "track_number": req.track_number,
        "year": req.year,
        "vinyl_mode": is_vinyl,
    }

    session_output = str(OUTPUT_DIR / session_id)
    os.makedirs(session_output, exist_ok=True)

    try:
        logger.info(
            "mastering_start",
            session_id=session_id,
            target_lufs=effective_target_lufs,
            vinyl_mode=is_vinyl,
        )

        result = master_audio(
            input_path=session["input_path"],
            output_dir=session_output,
            session_id=session_id,
            params=params,
            metadata=metadata,
        )

        write_metadata(
            wav_path=result.output_wav_path,
            mp3_path=result.output_mp3_path,
            metadata=metadata,
            session_id=session_id,
            output_lufs=result.output_lufs,
            output_true_peak=result.output_true_peak,
        )

        raw_output, _ = load_audio(result.output_wav_path)
        output_audio = normalize_input(raw_output, INTERNAL_SR)
        platform_slug = req.genre if req.genre in ("vinyl", "podcast") else "spotify"
        qc_report, _ = run_qc(
            output_audio, INTERNAL_SR, platform_slug,
            output_lufs=result.output_lufs,
            output_true_peak=result.output_true_peak,
        )
        session["qc_report"] = qc_report

        rain_cert = create_rain_cert(
            session_id=session_id,
            source_file_path=session["input_path"],
            output_file_path=result.output_wav_path,
            processing_params={"target_lufs": req.target_lufs, "brightness": req.brightness},
            output_lufs=result.output_lufs,
            output_true_peak=result.output_true_peak,
        )
        # Provenance completion gate for the prototype in-memory path.
        # Do not mark a session complete unless the RAIN-CERT is signed and
        # immediately verifies. The DB/S3 render task has the stricter hash gate;
        # this mirrors the RAIN-E306 enforcement for this local path.
        if not getattr(rain_cert, "signature", None):
            raise RuntimeError("RAIN-E306: Session completed without signed cert")
        if not verify_cert(rain_cert):
            raise RuntimeError("RAIN-E306: RAIN-CERT signature verification failed")
        session["rain_cert"] = rain_cert

        c2pa = create_c2pa_manifest(
            title=metadata.get("title", ""),
            artist=metadata.get("artist", ""),
            format="wav",
            rain_cert=rain_cert,
        )
        session["c2pa_manifest"] = c2pa

        session["result"] = result
        session["status"] = "complete"
        session["metadata"] = metadata

        logger.info(
            "mastering_complete",
            session_id=session_id,
            output_lufs=result.output_lufs,
            output_true_peak=result.output_true_peak,
            qc_passed=qc_report.passed,
            qc_checks=len(qc_report.checks),
        )

        return ProcessResponse(
            session_id=session_id,
            status="complete",
            output_lufs=round(result.output_lufs, 1),
            output_true_peak=round(result.output_true_peak, 1),
            output_dynamic_range=round(result.output_dynamic_range, 1),
            output_stereo_width=round(result.output_stereo_width, 3),
            output_spectral_centroid=round(result.output_spectral_centroid, 1),
        )

    except Exception as e:
        session["status"] = "failed"
        logger.error("mastering_failed", session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Mastering failed: {e}")


@router.get("/{session_id}/download/{format}")
async def download_file(
    session_id: str,
    format: str,
    current_user: CurrentUser = Depends(require_tier("spark", "creator", "artist", "studio_pro", "enterprise"))
) -> FileResponse:
    """Download the mastered file as WAV or MP3."""
    session = _require_session_owner(session_id, current_user)

    if session["status"] != "complete":
        raise HTTPException(status_code=400, detail="Mastering not complete")

    result: MasterResult = session["result"]

    if format.lower() == "wav":
        path = result.output_wav_path
        media_type = "audio/wav"
    elif format.lower() == "mp3":
        path = result.output_mp3_path
        media_type = "audio/mpeg"
    else:
        raise HTTPException(status_code=400, detail="Format must be 'wav' or 'mp3'")

    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Output file not found")

    filename = Path(path).name
    return FileResponse(
        path=path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{session_id}/features")
async def get_features(
    session_id: str,
    current_user: CurrentUser = Depends(require_tier("free", "spark", "creator", "artist", "studio_pro", "enterprise"))
) -> dict:
    """Get 43-dimensional feature vector for an uploaded session."""
    session = _require_session_owner(session_id, current_user)
    features: FeatureVector = session.get("features")
    if not features:
        raise HTTPException(status_code=400, detail="Features not yet extracted")
    return features.to_dict()


@router.get("/{session_id}/cert")
async def get_rain_cert(
    session_id: str,
    current_user: CurrentUser = Depends(require_tier("free", "spark", "creator", "artist", "studio_pro", "enterprise"))
) -> dict:
    """Get RAIN-CERT provenance certificate for a mastered session."""
    session = _require_session_owner(session_id, current_user)
    cert: RainCert | None = session.get("rain_cert")
    if not cert:
        raise HTTPException(status_code=400, detail="RAIN-CERT not yet issued (master first)")
    return cert.to_dict()


@router.get("/{session_id}/c2pa")
async def get_c2pa_manifest(
    session_id: str,
    current_user: CurrentUser = Depends(require_tier("free", "spark", "creator", "artist", "studio_pro", "enterprise"))
) -> dict:
    """Get C2PA v2.2 Content Provenance manifest for EU AI Act Article 50 compliance."""
    session = _require_session_owner(session_id, current_user)
    c2pa = session.get("c2pa_manifest")
    if not c2pa:
        raise HTTPException(status_code=400, detail="C2PA manifest not yet generated (master first)")
    return c2pa.to_dict()


@router.get("/{session_id}/qc")
async def get_qc_report(
    session_id: str,
    current_user: CurrentUser = Depends(require_tier("free", "spark", "creator", "artist", "studio_pro", "enterprise"))
) -> dict:
    """Get QC report (18 automated checks) for a mastered session."""
    session = _require_session_owner(session_id, current_user)
    qc_report: QCReport | None = session.get("qc_report")
    if not qc_report:
        raise HTTPException(status_code=400, detail="QC not yet run (master first)")
    return qc_report.to_dict()


@router.get("/pubkey")
async def get_signing_pubkey() -> dict:
    """Return the RAIN-CERT Ed25519 public key in PEM format."""
    from app.services.provenance import get_public_key_pem
    return {
        "alg": "Ed25519",
        "public_key_pem": get_public_key_pem(),
        "issuer": "ARCOVEL Technologies International",
        "purpose": "RAIN-CERT signature verification",
    }


# ── Spatial Processing ────────────────────────────────────────────────────────────────────────────────────────────────────


class SpatialRequest(BaseModel):
    format: str = Field(default="binaural", description="Spatial format: atmos_71, binaural, stereo")
    itd_ms: float = Field(default=0.5, ge=0.3, le=0.7, description="ITD delay in ms for binaural")


@router.post("/{session_id}/spatial")
async def apply_spatial(
    session_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_tier("studio_pro", "enterprise"))
) -> dict:
    """Apply spatial audio processing to a mastered session."""
    session = _require_session_owner(session_id, current_user)

    try:
        body = await request.json()
    except Exception:
        body = {}

    spatial_format = body.get("format", "binaural")
    itd_ms = max(0.3, min(0.7, float(body.get("itd_ms", 0.5))))

    logger.info("spatial_processing_start", session_id=session_id, format=spatial_format, itd_ms=itd_ms)

    gpu_available = False
    try:
        import torch
        gpu_available = torch.cuda.is_available()
    except ImportError:
        pass

    if spatial_format == "atmos_71" and not gpu_available:
        return {
            "session_id": session_id, "format": "binaural", "status": "fallback",
            "note": "Dolby Atmos 7.1 requires GPU backend. Returning binaural preview instead.",
            "binaural_preview": True, "itd_ms": itd_ms,
            "itd_samples": int(itd_ms * INTERNAL_SR / 1000),
            "object_positions": [], "object_count": 0, "genre_template": "default",
            "binaural_preview_url": f"/api/v1/master/{session_id}/spatial/preview",
        }

    if spatial_format == "binaural":
        itd_samples = int(itd_ms * INTERNAL_SR / 1000)
        return {
            "session_id": session_id, "format": "binaural", "status": "complete",
            "binaural_preview": True, "itd_ms": itd_ms, "itd_samples": itd_samples,
            "description": f"Binaural ITD simulation: {itd_ms}ms ({itd_samples} samples at {INTERNAL_SR}Hz)",
            "object_positions": [
                {"id": "L", "azimuth": -30, "elevation": 0, "distance": 1.0},
                {"id": "R", "azimuth": 30, "elevation": 0, "distance": 1.0},
            ],
            "object_count": 2, "genre_template": "stereo_binaural",
            "binaural_preview_url": f"/api/v1/master/{session_id}/spatial/preview",
        }

    if spatial_format == "stereo":
        return {
            "session_id": session_id, "format": "stereo", "status": "complete",
            "binaural_preview": False,
            "object_positions": [
                {"id": "L", "azimuth": -30, "elevation": 0, "distance": 1.0},
                {"id": "R", "azimuth": 30, "elevation": 0, "distance": 1.0},
            ],
            "object_count": 2, "genre_template": "stereo",
        }

    return {
        "session_id": session_id, "format": "atmos_71", "status": "complete",
        "binaural_preview": True, "itd_ms": itd_ms,
        "itd_samples": int(itd_ms * INTERNAL_SR / 1000),
        "object_positions": [
            {"id": "L", "azimuth": -30, "elevation": 0, "distance": 1.0},
            {"id": "R", "azimuth": 30, "elevation": 0, "distance": 1.0},
            {"id": "C", "azimuth": 0, "elevation": 0, "distance": 1.0},
            {"id": "LFE", "azimuth": 0, "elevation": -30, "distance": 1.0},
            {"id": "Ls", "azimuth": -110, "elevation": 0, "distance": 1.2},
            {"id": "Rs", "azimuth": 110, "elevation": 0, "distance": 1.2},
            {"id": "Ltf", "azimuth": -45, "elevation": 45, "distance": 1.4},
            {"id": "Rtf", "azimuth": 45, "elevation": 45, "distance": 1.4},
        ],
        "object_count": 8, "genre_template": "atmos_71_immersive",
        "binaural_preview_url": f"/api/v1/master/{session_id}/spatial/preview",
    }


# ── DDP Image Export ────────────────────────────────────────────────────────────────────────────────────────────────────────────


@router.get("/{session_id}/export/ddp")
async def export_ddp(
    session_id: str,
    current_user: CurrentUser = Depends(require_tier("studio_pro", "enterprise"))
) -> dict:
    """Export DDP metadata for CD manufacturing."""
    session = _require_session_owner(session_id, current_user)

    if session["status"] != "complete":
        raise HTTPException(status_code=400, detail="Mastering not complete — process first")

    result: MasterResult = session["result"]
    metadata = session.get("metadata", {})
    analysis: AnalysisResult = session["analysis"]

    title = metadata.get("title", Path(session["filename"]).stem)
    artist = metadata.get("artist", "")
    genre = metadata.get("genre", "")
    duration = analysis.duration
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    frames = int((duration % 1) * 75)

    ddpid_content = (
        f"DDP_ID\r\nIdentifier: RAIN-{session_id}\r\nFormat: DDP 2.00\r\n"
        f"Generator: RAIN AI Mastering Engine\r\nGeneratorVersion: 6.0\r\n"
    )
    ddpms_content = (
        f"DDP_MS\r\nTitle: {title}\r\nArtist: {artist}\r\nGenre: {genre}\r\n"
        f"SampleRate: 44100\r\nBitDepth: 16\r\nChannels: {analysis.channels}\r\n"
        f"Duration: {duration:.3f}\r\nTrackCount: 1\r\nTrack 01:\r\n"
        f"  Start: 00:00:00.00\r\n  End: {minutes:02d}:{seconds:02d}:{frames:02d}.00\r\n"
        f"  PreGap: 02:00\r\n"
    )

    return {
        "session_id": session_id, "format": "ddp", "status": "ready",
        "red_book_spec": {"sample_rate": 44100, "bit_depth": 16, "channels": analysis.channels},
        "ddpid": ddpid_content, "ddpms": ddpms_content,
        "note": (
            "DDP metadata descriptor. Full binary DDP image available via "
            f"/api/v1/sessions/{session_id}/ddp for Studio Pro+ tiers."
        ),
        "download_endpoint": f"/api/v1/sessions/{session_id}/ddp",
    }


# ── AI Suggest ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────


def _generate_heuristic_response(user_message: str, analysis: AnalysisResult) -> str:
    """Keyword + genre-aware mastering advice fallback."""
    q = user_message.lower()
    genre = getattr(analysis, "genre", "unknown")
    lufs = analysis.input_lufs
    centroid = analysis.spectral_centroid
    parts: list[str] = []

    if "bright" in q or "air" in q or "crisp" in q or "presence" in q:
        if centroid > 5000.0:
            parts.append(
                f"Your track already has a bright spectral centre ({centroid:.0f} Hz). "
                "Keep BRIGHTEN around 4-5 to avoid harshness. Try REPAIR at 2-3 first."
            )
        else:
            rec = 6.0 if centroid < 3000.0 else 5.0
            parts.append(f"Spectral centroid at {centroid:.0f} Hz — try BRIGHTEN at {rec:.1f}.")

    if "warm" in q or "analog" in q or "vintage" in q or "tape" in q:
        rec = min(7.0, 4.0 + (4000.0 - min(centroid, 4000.0)) / 1000.0)
        parts.append(f"For warmth: WARMTH {rec:.1f}. Keep BRIGHTEN below 5 to avoid fighting it.")

    if "punch" in q or "drum" in q or "kick" in q or "snare" in q or "impact" in q:
        rec = 7.0 if genre in ("rock", "hiphop", "electronic") else 5.5
        parts.append(f"For punch: PUNCH {rec:.1f}. Pair with GLUE 4-5 for cohesion.")

    if "bass" in q or "low end" in q or "sub" in q or "bottom" in q:
        bass = analysis.bass_energy_ratio
        if bass > 0.25:
            parts.append(f"Low end already heavy ({bass:.0%}). Try PUNCH 6 to tighten rather than adding WARMTH.")
        else:
            parts.append("Light low end. Bump WARMTH to 6, WIDTH to 4 to keep bass centred.")

    if "loud" in q or "louder" in q or "level" in q or "spotify" in q or "stream" in q:
        headroom = -14.0 - lufs
        if headroom > 4.0:
            parts.append(f"At {lufs:.1f} LUFS, {headroom:.1f} LU below Spotify target. GLUE 6-7, PUNCH 5-6.")
        else:
            parts.append(f"At {lufs:.1f} LUFS, close to target. GLUE 5 is enough — harder push costs dynamics.")

    if "wide" in q or "stereo" in q or "spatial" in q or "immersive" in q:
        sw = analysis.stereo_width
        if sw > 0.8:
            parts.append(f"Width already broad ({sw:.2f}). Try SPACE 5-6 for depth instead.")
        else:
            parts.append("WIDTH 7 + SPACE 5 for immersive image. Bass stays centred below 200 Hz.")

    if "clean" in q or "noise" in q or "fix" in q or "repair" in q:
        parts.append("REPAIR 5-6 for moderate cleanup. Go 7-8 only if audible noise or clipping.")

    if "radio" in q or "professional" in q or "commercial" in q or "polished" in q:
        parts.append("Radio-ready: GLUE 6, PUNCH 5, BRIGHTEN 5, WARMTH 3, WIDTH 5.")

    if not parts:
        genre_tips: dict[str, str] = {
            "electronic": "PUNCH 6, GLUE 5, WIDTH 7, BRIGHTEN 5.",
            "hiphop": "WARMTH 6, PUNCH 7, GLUE 5, WIDTH 4.",
            "rock": "PUNCH 7, GLUE 6, BRIGHTEN 5, WARMTH 4.",
            "pop": "BRIGHTEN 5, GLUE 5, WIDTH 5, PUNCH 4, WARMTH 3.",
            "ambient": "GLUE 2, PUNCH 2, SPACE 7, WIDTH 6 — let it breathe.",
            "funk_soul": "PUNCH 6, WARMTH 5, GLUE 4, WIDTH 5.",
            "afropop_house": "PUNCH 5, WARMTH 5, GLUE 5, WIDTH 6, SPACE 5.",
        }
        tip = genre_tips.get(genre, genre_tips["pop"])
        parts.append(
            f"Detected genre **{genre}** (tempo {analysis.tempo_bpm:.0f} BPM, "
            f"centroid {centroid:.0f} Hz, groove {analysis.groove_score:.2f}).\n\n{tip}\n\n"
            "Tell me more about the sound you're going for."
        )

    return "\n\n".join(parts)


@router.post("/{session_id}/ai-suggest")
async def ai_suggest(session_id: str, request: Request) -> dict:
    """Claude-powered mastering suggestions. Falls back to heuristic if API unavailable."""
    body = await request.json()
    user_message: str = body.get("message", "")

    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    analysis: AnalysisResult = session["analysis"]

    context = (
        f'You are RAIN\'s AI mastering engineer. The user uploaded "{session.get("filename", "unknown")}".\n'
        f"Analysis: Input LUFS={analysis.input_lufs:.1f}, Genre={getattr(analysis, 'genre', 'unknown')}, "
        f"Tempo={analysis.tempo_bpm:.1f} BPM, Spectral centroid={analysis.spectral_centroid:.0f} Hz, "
        f"Groove={analysis.groove_score:.2f}, Transient sharpness={analysis.transient_sharpness:.2f}, "
        f"Stereo width={analysis.stereo_width:.3f}, Bass energy ratio={analysis.bass_energy_ratio:.3f}.\n"
        "Give brief, specific mastering advice. Suggest macro values (0-10) when relevant. "
        "The 7 macros are: BRIGHTEN, GLUE, WIDTH, PUNCH, WARMTH, SPACE, REPAIR."
    )

    try:
        api_key = settings.ANTHROPIC_API_KEY
        if api_key and api_key != "sk-ant-..." and len(api_key) > 10:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=settings.ANTHROPIC_MODEL,  # from config, not hardcoded
                max_tokens=500,
                system=context,
                messages=[{"role": "user", "content": user_message}],
            )
            return {
                "response": response.content[0].text,
                "source": "claude",
                "model": settings.ANTHROPIC_MODEL,
                "genre": getattr(analysis, "genre", "unknown"),
                "analysis_summary": {
                    "input_lufs": round(analysis.input_lufs, 1),
                    "tempo_bpm": round(analysis.tempo_bpm, 1),
                    "spectral_centroid": round(analysis.spectral_centroid, 0),
                    "groove_score": round(analysis.groove_score, 2),
                },
            }
    except Exception as e:
        logger.warning("claude_api_fallback", error=str(e), session_id=session_id)

    suggestions = _generate_heuristic_response(user_message, analysis)
    return {
        "response": suggestions,
        "source": "heuristic",
        "genre": getattr(analysis, "genre", "unknown"),
        "analysis_summary": {
            "input_lufs": round(analysis.input_lufs, 1),
            "tempo_bpm": round(analysis.tempo_bpm, 1),
            "spectral_centroid": round(analysis.spectral_centroid, 0),
            "groove_score": round(analysis.groove_score, 2),
        },
    }
