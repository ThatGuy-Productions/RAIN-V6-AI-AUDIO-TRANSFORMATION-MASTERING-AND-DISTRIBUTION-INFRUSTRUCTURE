"""
RAIN — R∞N AI Mastering Engine
backend/app/api/middleware.py

Request middleware stack.
Implements: rate limiting, request-ID injection, security headers.
This is the enforcement layer that gates every inbound request before it
reaches any route handler.

Audit fix: Issue #1 (CRITICAL) — middleware.py was 0 bytes / unimplemented.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Number of requests allowed per window per client IP
RATE_LIMIT_REQUESTS: int = 120
# Rolling window in seconds
RATE_LIMIT_WINDOW_SECONDS: int = 60

# Security response headers applied to every response
SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "connect-src 'self' https://api.anthropic.com https://*.stripe.com; "
        "script-src 'self' 'wasm-unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "worker-src 'self' blob:;"
    ),
}


# ---------------------------------------------------------------------------
# In-process rate-limit store
# ---------------------------------------------------------------------------
# Production deployments should replace this with a Valkey/Redis-backed store
# so limits are enforced across multiple workers.  The interface is intentionally
# thin so the swap is trivial.

class _InMemoryRateLimitStore:
    """Sliding-window counter keyed by client IP."""

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, limit: int, window: int) -> bool:
        now = time.monotonic()
        cutoff = now - window
        # Evict expired timestamps
        self._buckets[key] = [t for t in self._buckets[key] if t > cutoff]
        if len(self._buckets[key]) >= limit:
            return False
        self._buckets[key].append(now)
        return True


_rate_store = _InMemoryRateLimitStore()


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RAINMiddleware(BaseHTTPMiddleware):
    """
    Unified RAIN request middleware.  Applied once at app startup.

    Order of operations for every request:
      1. Inject X-Request-ID (generate if absent)
      2. Rate-limit by client IP  → 429 if exceeded
      3. Call the downstream route handler
      4. Attach security headers to the response
      5. Emit a structured access log entry
    """

    def __init__(
        self,
        app: ASGIApp,
        rate_limit_requests: int = RATE_LIMIT_REQUESTS,
        rate_limit_window: int = RATE_LIMIT_WINDOW_SECONDS,
    ) -> None:
        super().__init__(app)
        self._rate_limit_requests = rate_limit_requests
        self._rate_limit_window = rate_limit_window

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.monotonic()

        # ── 1. Request ID ──────────────────────────────────────────────────
        request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Bind to structlog context for the lifetime of this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # ── 2. Rate limiting ───────────────────────────────────────────────
        client_ip: str = self._resolve_client_ip(request)
        if not _rate_store.is_allowed(
            client_ip,
            self._rate_limit_requests,
            self._rate_limit_window,
        ):
            log.warning(
                "rate_limit_exceeded",
                client_ip=client_ip,
                path=request.url.path,
                error_code="RAIN-E429",
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "RAIN-E429",
                    "detail": "Rate limit exceeded. Please slow down.",
                    "request_id": request_id,
                },
                headers={
                    "X-Request-ID": request_id,
                    "Retry-After": str(self._rate_limit_window),
                },
            )

        # ── 3. Route handler ───────────────────────────────────────────────
        response: Response = await call_next(request)

        # ── 4. Security headers ────────────────────────────────────────────
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        response.headers["X-Request-ID"] = request_id

        # ── 5. Access log ──────────────────────────────────────────────────
        duration_ms = round((time.monotonic() - start) * 1000, 2)
        log.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            client_ip=client_ip,
            duration_ms=duration_ms,
        )

        return response

    # -----------------------------------------------------------------------

    @staticmethod
    def _resolve_client_ip(request: Request) -> str:
        """
        Resolve the real client IP, preferring the X-Forwarded-For header
        when the request arrives via the nginx reverse proxy.
        Falls back to the direct connection address.
        """
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # The leftmost address is the originating client
            return forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------

def register_middleware(app: ASGIApp) -> None:
    """
    Attach RAINMiddleware to a FastAPI/Starlette application.

    Usage in backend/app/main.py:
        from app.api.middleware import register_middleware
        register_middleware(app)
    """
    app.add_middleware(RAINMiddleware)  # type: ignore[arg-type]
