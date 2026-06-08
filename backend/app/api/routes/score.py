"""Public RAIN Score API — no authentication required, rate-limited by IP.

Rate limit is enforced via Valkey (shared across all worker processes).
CPU-intensive scoring is offloaded from the event loop via run_in_executor.
"""
from __future__ import annotations

import asyncio
import functools
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

logger = structlog.get_logger()
router = APIRouter(prefix="/score", tags=["score"])

_RATE_WINDOW = 3600   # 1 hour in seconds
_RATE_MAX = 10
_RATE_KEY_PREFIX = "rain:score:rl:"


async def _check_rate_limit_valkey(ip: str) -> None:
    """Enforce 10 req/hour per IP using a Valkey sliding-window counter.

    Atomic INCR + conditional EXPIRE ensures correctness across all worker
    processes. Falls back to allowing the request if Valkey is unavailable
    (fail-open is acceptable for a public scoring endpoint).
    """
    try:
        from app.core.config import settings
        import redis.asyncio as aioredis

        r = aioredis.from_url(settings.VALKEY_URL, decode_responses=True)
        key = f"{_RATE_KEY_PREFIX}{ip}"
        async with r:
            count = await r.incr(key)
            if count == 1:
                # First hit — set TTL so the window expires automatically
                await r.expire(key, _RATE_WINDOW)
            if count > _RATE_MAX:
                raise HTTPException(
                    429,
                    detail={
                        "code": "RAIN-E503",
                        "message": f"Rate limit: {_RATE_MAX} scores per hour per IP",
                    },
                )
    except HTTPException:
        raise
    except Exception as exc:
        # Valkey unavailable — log and fail-open (don't block legitimate users)
        logger.warning(
            "score_rate_limit_valkey_error",
            error=str(exc),
            ip=ip,
            note="failing open — rate limit not enforced for this request",
        )


def _compute_score_sync(data: bytes, platform: str):
    """Synchronous CPU-bound scoring — runs in executor thread pool."""
    from app.services.rain_score_v2 import compute_rain_score_sync
    from app.services.audio_analysis import extract_mel_spectrogram_sync

    mel, duration, sr = extract_mel_spectrogram_sync(data)
    score = compute_rain_score_sync(data, platform, mel)
    return score, duration


@router.post("/")
async def public_rain_score(
    request: Request,
    file: UploadFile = File(...),
    platform: str = "spotify",
) -> dict:
    """Public RAIN Score endpoint. No authentication required.

    Rate limit: 10 requests per hour per IP (enforced via Valkey).
    Accepts: WAV, FLAC, MP3 (max 20 MB for public endpoint).

    CPU-intensive mel extraction and scoring run in a thread pool executor
    so the event loop is never blocked.
    """
    client_ip = request.client.host if request.client else "unknown"
    await _check_rate_limit_valkey(client_ip)

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(
            413, detail={"code": "RAIN-E201", "message": "File exceeds 20 MB public limit"}
        )

    try:
        loop = asyncio.get_event_loop()
        score, duration = await loop.run_in_executor(
            None, functools.partial(_compute_score_sync, data, platform)
        )
        return {
            "score": score,
            "platform": platform,
            "duration_seconds": round(duration, 1),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("public_score_failed", error=str(e), ip=client_ip)
        raise HTTPException(
            500, detail={"code": "RAIN-E300", "message": "Score computation failed"}
        )
