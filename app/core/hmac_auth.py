"""HMAC verification for Django → tars admin proxy requests.

Matches django-rest-api `TarsClient` signing:
  message = f"{timestamp}:{METHOD}:{path}:{body_str}"
  signature = HMAC-SHA256(secret, message).hexdigest()

Only admin paths are verified. Health checks and future SDK hot paths are skipped.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

logger = logging.getLogger(__name__)

SIGNATURE_HEADER = "x-clickwrap-signature"
TIMESTAMP_HEADER = "x-clickwrap-timestamp"

# Admin control-plane prefixes that require HMAC (Django proxy).
ADMIN_PATH_PREFIXES = ("/api/v2/",)

# Explicitly excluded even if under a broader prefix later.
EXCLUDED_PATH_PREFIXES = (
    "/ht",
    "/api/v3/public/",
    "/docs",
    "/openapi.json",
    "/redoc",
)


def is_admin_path(path: str) -> bool:
    if any(path == prefix or path.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
        return False
    return any(path.startswith(prefix) for prefix in ADMIN_PATH_PREFIXES)


def build_signature_message(timestamp: str, method: str, path: str, body_str: str) -> bytes:
    return f"{timestamp}:{method.upper()}:{path}:{body_str}".encode()


def compute_signature(secret: str, message: bytes) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        message,
        digestmod=hashlib.sha256,
    ).hexdigest()


def verify_hmac_headers(
    *,
    method: str,
    path: str,
    body_str: str,
    signature: str | None,
    timestamp: str | None,
    secret: str,
    tolerance_seconds: int,
    now: int | None = None,
) -> str | None:
    """Return an error detail string if verification fails, else None."""
    if not signature or not timestamp:
        return "Missing HMAC signature headers"

    try:
        ts = int(timestamp)
    except ValueError:
        return "Invalid HMAC timestamp"

    current = now if now is not None else int(time.time())
    if abs(current - ts) > tolerance_seconds:
        return "HMAC timestamp outside allowed window"

    expected = compute_signature(
        secret,
        build_signature_message(timestamp, method, path, body_str),
    )
    if not hmac.compare_digest(expected, signature):
        return "Invalid HMAC signature"

    return None


class AdminHMACMiddleware:
    """Pure ASGI middleware so the request body can be replayed to downstream apps."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope["path"]
        if not is_admin_path(path):
            await self.app(scope, receive, send)
            return

        body = await _read_body(receive)
        headers = Headers(scope=scope)
        method = scope["method"]
        body_str = body.decode("utf-8") if body else ""

        error = verify_hmac_headers(
            method=method,
            path=path,
            body_str=body_str,
            signature=headers.get(SIGNATURE_HEADER),
            timestamp=headers.get(TIMESTAMP_HEADER),
            secret=settings.TARS_HMAC_SECRET,
            tolerance_seconds=settings.TARS_HMAC_TIMESTAMP_TOLERANCE_SECONDS,
        )
        if error is not None:
            logger.warning(
                "Admin HMAC verification failed",
                extra={
                    "path": path,
                    "method": method,
                    "reason": error,
                },
            )
            response = JSONResponse(status_code=401, content={"detail": error})
            await response(scope, receive, send)
            return

        await self.app(scope, _replay_receive(body), send)


async def _read_body(receive: Receive) -> bytes:
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] != "http.request":
            continue
        body.extend(message.get("body", b""))
        if not message.get("more_body", False):
            break
    return bytes(body)


def _replay_receive(body: bytes) -> Receive:
    sent = False

    async def receive() -> Message:
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return receive
