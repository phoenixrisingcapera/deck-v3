from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.datastructures import Headers, MutableHeaders

from app.api.routes.deck_artifacts import public_renderer_router
from app.core.config import settings
from app.core.security import generate_id
from app.db.session import get_engine
from app.services.storage.artifact_storage import S3UploadStorage, get_upload_storage

request_logger = logging.getLogger("app.instant_html_renderer.request")

app = FastAPI(
    title="Deck Instant HTML Renderer",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(public_renderer_router, prefix="/api")


def _error_payload(request: Request, status_code: int, message: str) -> dict[str, object]:
    return {
        "ok": False,
        "error": {"code": f"http_{status_code}", "message": message},
        "requestId": getattr(request.state, "request_id", None),
    }


@app.exception_handler(HTTPException)
async def renderer_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    message = str(detail.get("message") or "Request failed.") if isinstance(detail, dict) else str(detail)
    return JSONResponse(_error_payload(request, exc.status_code, message), status_code=exc.status_code, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def renderer_validation_error(request: Request, _exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(_error_payload(request, 422, "Request validation failed."), status_code=422)


@app.exception_handler(Exception)
async def renderer_unhandled_error(request: Request, _exc: Exception) -> JSONResponse:
    request_logger.error(
        "instant_html_renderer_unhandled_error",
        extra={"event": "instant_html_renderer_unhandled_error", "request_id": getattr(request.state, "request_id", None)},
    )
    return JSONResponse(_error_payload(request, 500, "Request failed."), status_code=500)


def _redacted_path(path: str) -> str:
    if path.startswith("/api/instant-html-render/"):
        return "/api/instant-html-render/[REDACTED]"
    return path


def _security_headers(headers: MutableHeaders, *, request_id: str) -> None:
    headers.setdefault("X-Request-ID", request_id)
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("Referrer-Policy", "no-referrer")
    headers.setdefault("Cache-Control", "no-store")
    headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
    if settings.is_production:
        headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


class RendererBoundaryMiddleware:
    """Pure-ASGI renderer boundary without BaseHTTPMiddleware stream tasks."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        started_at = time.perf_counter()
        headers = Headers(scope=scope)
        request_id = headers.get("x-request-id", "").strip()[:128] or generate_id("req")
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["capability_status"] = None
        original_path = str(scope.get("path") or "")
        redacted_path = _redacted_path(original_path)
        request = Request(scope, receive=receive)

        async def send_with_security_headers(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                _security_headers(MutableHeaders(scope=message), request_id=request_id)
            await send(message)

        try:
            if original_path.startswith("/api/instant-html-render/") and (
                headers.get("authorization") or headers.get("cookie")
            ):
                response = JSONResponse(
                    _error_payload(request, 400, "The cookieless renderer does not accept credentials."),
                    status_code=400,
                )
                state["capability_status"] = "credential_rejected"
                await response(scope, receive, send_with_security_headers)
                return
            await self.app(scope, receive, send_with_security_headers)
        finally:
            request_logger.info(
                "http_request",
                extra={
                    "event": "http_request",
                    "request_id": request_id,
                    "method": str(scope.get("method") or ""),
                    "path": redacted_path,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    "capability_status": state.get("capability_status"),
                },
            )


app.add_middleware(RendererBoundaryMiddleware)


def _expected_core_heads() -> set[str]:
    return set(ScriptDirectory.from_config(AlembicConfig("alembic.ini")).get_heads())


def _probe_renderer_database() -> None:
    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
        current = set(connection.execute(text("SELECT version_num FROM alembic_version_core")).scalars())
    if current != _expected_core_heads():
        raise RuntimeError("core_migration_mismatch")


def _probe_renderer_key_and_config() -> None:
    if not settings.instant_html_enabled or not settings.instant_html_render_parent_origin:
        raise RuntimeError("renderer_config_unusable")
    fernet = Fernet(settings.instant_html_render_fernet_key.encode("utf-8"))
    sample = b"renderer-readiness"
    if fernet.decrypt(fernet.encrypt(sample)) != sample:
        raise RuntimeError("renderer_key_unusable")


def _probe_renderer_storage() -> None:
    """Authenticate a read-only provider request; never create/delete objects."""

    storage = get_upload_storage()
    if storage.provider == "s3":
        assert isinstance(storage, S3UploadStorage)
        storage._client_or_create().list_objects_v2(  # noqa: SLF001 - readiness owns provider boundary
            Bucket=settings.upload_storage_s3_bucket,
            Prefix=settings.upload_storage_s3_prefix.strip("/") + "/",
            MaxKeys=1,
        )
        return
    if storage.provider == "supabase":
        bucket = quote(settings.supabase_storage_bucket.strip("/"), safe="")
        request = UrlRequest(
            f"{settings.supabase_url.rstrip('/')}/storage/v1/bucket/{bucket}",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_role_key}",
                "apikey": settings.supabase_service_role_key,
            },
            method="GET",
        )
        with urlopen(request, timeout=5):
            return
    raise RuntimeError("renderer_storage_backend_unsupported")


def renderer_readiness_checks() -> dict[str, str]:
    checks: dict[str, str] = {}
    for name, probe in (
        ("database", _probe_renderer_database),
        ("rendererConfig", _probe_renderer_key_and_config),
        ("artifactStorage", _probe_renderer_storage),
    ):
        try:
            probe()
            checks[name] = "ready"
        except Exception as exc:
            checks[name] = "failed"
            request_logger.warning(
                "instant_html_renderer_readiness_failed",
                extra={"event": "instant_html_renderer_readiness_failed", "readiness_check": name, "error_type": type(exc).__name__},
            )
    return checks


@app.get("/health/live", tags=["health"])
def renderer_liveness() -> dict[str, str]:
    return {"status": "ok", "service": "instant-html-renderer"}


@app.get("/health/ready", tags=["health"])
def renderer_readiness():
    checks = renderer_readiness_checks()
    if any(status != "ready" for status in checks.values()):
        return JSONResponse(
            {"status": "not_ready", "service": "instant-html-renderer", "checks": checks},
            status_code=503,
        )
    return {"status": "ready", "service": "instant-html-renderer", "checks": checks}
