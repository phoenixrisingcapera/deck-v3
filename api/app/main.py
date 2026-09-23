import logging
import time

from app.core.security import generate_id
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.product import PRODUCT_ROUTERS
from app.api.deps import require_resource_access
from app.core.config import settings
from app.db.session import SessionLocal
from app.observability import instrument_fastapi_app
from app.services.admin.failure_tickets import create_failure_ticket_from_exception

request_logger = logging.getLogger("app.request")

app = FastAPI(title=settings.app_name)
instrument_fastapi_app(app)


def _canonical_error_payload(request: Request, status_code: int, detail, *, code: str) -> dict:
    if isinstance(detail, dict):
        message = str(detail.get("message") or detail.get("error") or "Request failed.")
    else:
        message = str(detail or "Request failed.")
    request_id = getattr(request.state, "request_id", None)
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "recoverable": status_code in {408, 409, 425, 429, 502, 503, 504},
            "nextAction": "retry" if status_code in {408, 425, 429, 502, 503, 504} else None,
        },
        "requestId": request_id,
    }


@app.exception_handler(HTTPException)
async def canonical_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        _canonical_error_payload(request, exc.status_code, exc.detail, code=f"http_{exc.status_code}"),
        status_code=exc.status_code,
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def canonical_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    validation_errors = [
        {"type": item.get("type"), "loc": list(item.get("loc") or ()), "message": item.get("msg")}
        for item in exc.errors()
    ]
    return JSONResponse(
        _canonical_error_payload(request, 422, "Request validation failed.", code="validation_error")
        | {"validationErrors": validation_errors},
        status_code=422,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Requested-With", "X-Request-ID"],
)

app.include_router(health_router, prefix="/api")
for product_router, product_prefix in PRODUCT_ROUTERS:
    app.include_router(product_router, prefix=product_prefix, dependencies=[Depends(require_resource_access)])

app.include_router(auth_router, prefix="/api")


@app.middleware("http")
async def add_security_headers(request, call_next):
    started_at = time.perf_counter()
    incoming_request_id = request.headers.get("x-request-id", "").strip()
    request_id = incoming_request_id[:128] if incoming_request_id else generate_id("req")
    request.state.request_id = request_id
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > settings.max_request_body_size_bytes:
        response = JSONResponse({"detail": "Request body is too large"}, status_code=413)
        response = _apply_security_headers(request, response, request_id)
        _log_request(request, response.status_code, request_id, started_at)
        return response

    try:
        response = await call_next(request)
    except Exception as exc:
        _record_unhandled_exception_ticket(request, exc)
        _log_request(request, 500, request_id, started_at, level=logging.ERROR)
        _redact_capability_scope(request)
        raise
    response = _apply_security_headers(request, response, request_id)
    _log_request(request, response.status_code, request_id, started_at)
    _redact_capability_scope(request)
    return response


def _redact_capability_scope(request: Request) -> None:
    """Prevent ASGI server/access-log layers from receiving the opaque token."""
    path = request.scope.get("path", "")
    redacted = _redacted_secret_path(path)
    if redacted != path:
        request.scope["path"] = redacted
        request.scope["raw_path"] = redacted.encode("ascii")


def _redacted_secret_path(path: str) -> str:
    if path.startswith("/api/instant-html-render/"):
        return "/api/instant-html-render/[REDACTED]"
    if path.startswith("/api/public/deck-shares/"):
        return "/api/public/deck-shares/[REDACTED]"
    return path


def _log_request(request, status_code: int, request_id: str, started_at: float, *, level: int = logging.INFO) -> None:
    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
    client_host = request.client.host if request.client is not None else None
    request_logger.log(
        level,
        "http_request",
        extra={
            "event": "http_request",
            "request_id": request_id,
            "method": request.method,
            "path": _redacted_secret_path(request.url.path),
            "status_code": status_code,
            "duration_ms": duration_ms,
            "client_host": client_host,
        },
    )


def _apply_security_headers(request, response, request_id):
    response.headers.setdefault("X-Request-ID", request_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    if not request.url.path.startswith("/api/instant-html-render/"):
        response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'; base-uri 'none'")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def _record_unhandled_exception_ticket(request, exc: BaseException) -> None:
    if (
        request.url.path in {
            "/api/admin/failure-tickets/report",
            "/api/support/failure-tickets/report",
        }
        or request.url.path.startswith("/api/instant-html-render/")
        or request.url.path.startswith("/api/public/deck-shares/")
    ):
        return
    db = SessionLocal()
    try:
        create_failure_ticket_from_exception(db, request=request, exc=exc, commit=True)
    except Exception:
        request_logger.exception("failure_ticket_record_failed")
        db.rollback()
    finally:
        db.close()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Deck AI Stack FastAPI backend"}


@app.get("/health", tags=["health"])
def root_health() -> dict[str, str]:
    return {"status": "ok", "service": "deck-aistack-codes-backend"}


def assert_unique_method_paths(application: FastAPI) -> None:
    """Fail startup when router order would silently shadow an API handler."""
    owners: dict[tuple[str, str], list[str]] = {}
    for route in application.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            owners.setdefault((method, route.path), []).append(route.endpoint.__name__)
    duplicates = {key: names for key, names in owners.items() if len(names) > 1}
    if duplicates:
        details = "; ".join(
            f"{method} {path}: {', '.join(names)}"
            for (method, path), names in sorted(duplicates.items())
        )
        raise RuntimeError(f"Duplicate API method/path registrations: {details}")


assert_unique_method_paths(app)
