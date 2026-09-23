from datetime import datetime, timezone
import logging

from sqlalchemy import text
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.openai_full_html_policy import require_full_html_openai_model
from app.core.config import settings
from app.api.deps import get_ai_db, get_db
from app.db.models import WorkflowJob
from app.db.session import get_ai_engine, get_engine
from app.services.deck_processing.workflow_jobs import JOB_STATUS_FAILED_RETRYABLE, JOB_STATUS_QUEUED, JOB_STATUS_RUNNING
from app.services.storage.artifact_storage import get_upload_storage
from app.services.storage.upload_readiness import get_upload_persistence_readiness
from app.services.llm.embedding_service import probe_embedding_contract

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


def _coarse_health(ready: bool) -> dict[str, str]:
    return {"status": "ready" if ready else "not_ready"}


def _generation_provider_readiness() -> tuple[str, dict[str, object]]:
    """Passively report provider configuration without making provider calls."""
    mode = (settings.deck_generation_mode or "openai").strip().lower()
    if mode == "openai":
        exact_model = True
        try:
            require_full_html_openai_model(settings.openai_model)
        except ValueError:
            exact_model = False
        configured = bool(settings.openai_api_key)
        canary_ready = bool(
            configured
            and exact_model
            and settings.instant_html_enabled
        )
        return "openai", {
            "status": "ready" if canary_ready else "configured_unverified" if configured else "not_configured",
            "provider": "openai",
            "model": settings.openai_model,
            "modelExact": exact_model,
            "configured": configured,
            "verification": "passive",
            "canaryReady": canary_ready,
            "maxOperationCostCents": settings.instant_html_max_operation_cost_cents,
        }
    if mode in {"qwen", "dashscope", "alibaba"}:
        return "qwen", {
            "status": "ready" if settings.effective_qwen_api_key and settings.effective_qwen_model else "failed",
            "provider": "dashscope",
            "model": settings.effective_qwen_model,
        }
    return "llm", {"status": "failed", "provider": mode or "missing", "model": None}


def _expected_heads(config_path: str) -> tuple[str, ...]:
    config = AlembicConfig(config_path)
    return tuple(ScriptDirectory.from_config(config).get_heads())


def _migration_heads(connection, table_name: str) -> tuple[str, ...]:
    return tuple(connection.execute(text(f"SELECT version_num FROM {table_name} ORDER BY version_num")).scalars())


def _database_probe(engine) -> bool:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


@router.get("/health/live")
def liveness() -> dict[str, str]:
    """Process liveness only; never exposes configuration or credentials."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> dict[str, object]:
    """Core readiness gate used by Railway before routing traffic."""
    try:
        engine = get_engine()
        _database_probe(engine)
        with engine.connect() as connection:
            current_heads = _migration_heads(connection, "alembic_version_core")
            expected_heads = _expected_heads("alembic.ini")
            if set(current_heads) != set(expected_heads):
                raise RuntimeError("Core database migration head is not current")
            developer_tools_table = connection.execute(
                text("SELECT to_regclass('public.developer_tool_events')")
            ).scalar_one_or_none()
            if developer_tools_table != "developer_tool_events":
                raise RuntimeError("Core database developer-tools module is unavailable")
    except Exception as exc:
        logger.warning("ai_readiness_failed", extra={"errorType": exc.__class__.__name__})
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Core database is not ready")
    return _coarse_health(True)


@router.get("/health/ai")
def ai_readiness() -> dict[str, object]:
    """AI database readiness without exposing connection metadata."""
    stage = "engine"
    try:
        engine = get_ai_engine()
        stage = "connectivity"
        _database_probe(engine)
        with engine.connect() as connection:
            stage = "alembic_head"
            revisions = _migration_heads(connection, "alembic_version_ai")
            expected_heads = _expected_heads("alembic_ai.ini")
            if set(revisions) != set(expected_heads):
                raise RuntimeError("AI database migration head is not current")
            stage = "pgvector_extension"
            vector_extension = connection.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'")).scalar_one_or_none()
            if vector_extension != "vector":
                raise RuntimeError("AI database pgvector extension is unavailable")
            stage = "vector_chunks_table"
            vector_table = connection.execute(text("SELECT to_regclass('public.vector_chunks')")).scalar_one_or_none()
            if vector_table != "vector_chunks":
                raise RuntimeError("AI database vector_chunks table is unavailable")
            stage = "vector_dimensions"
            vector_type = connection.execute(
                text(
                    "SELECT format_type(a.atttypid, a.atttypmod) "
                    "FROM pg_attribute a "
                    "JOIN pg_class c ON c.oid = a.attrelid "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relname = 'vector_chunks' "
                    "AND a.attname = 'embedding' AND a.attnum > 0 AND NOT a.attisdropped"
                )
            ).scalar_one_or_none()
            if vector_type != "vector(1024)":
                raise RuntimeError("AI database embedding vector dimension is invalid")
        stage = "embedding_provider"
        embedding_probe = probe_embedding_contract()
    except Exception as exc:
        logger.warning(
            "ai_readiness_failed",
            extra={"readinessStage": stage, "errorType": exc.__class__.__name__},
        )
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="AI database is not ready")
    logger.info("ai_readiness_passed")
    return _coarse_health(True)


@router.get("/health")
def health() -> dict[str, object]:
    return _coarse_health(settings.startup_validation_ok)


@router.get("/health/product-ready")
def product_ready() -> dict[str, object]:
    """Aggregated Railway readiness for the real upload-to-export product."""
    checks: dict[str, dict[str, object]] = {}

    try:
        engine = get_engine()
        with engine.connect() as connection:
            current_core_heads = _migration_heads(connection, "alembic_version_core")
        core_heads = _expected_heads("alembic.ini")
        checks["core"] = {"status": "ready"}
        if set(current_core_heads) != set(core_heads):
            checks["core"]["status"] = "failed"
    except Exception as exc:
        checks["core"] = {"status": "failed", "errorType": exc.__class__.__name__}

    try:
        engine = get_ai_engine()
        with engine.connect() as connection:
            current_ai_heads = _migration_heads(connection, "alembic_version_ai")
            vector_extension = connection.execute(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            ).scalar_one_or_none()
            vector_dimension = connection.execute(
                text(
                    "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
                    "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relname='vector_chunks' AND a.attname='embedding' "
                    "AND a.attnum > 0 AND NOT a.attisdropped"
                )
            ).scalar_one_or_none()
        ai_heads = _expected_heads("alembic_ai.ini")
        checks["ai"] = {
            "status": "ready" if set(current_ai_heads) == set(ai_heads) and vector_extension and vector_dimension == "vector(1024)" else "failed",
        }
    except Exception as exc:
        checks["ai"] = {"status": "failed", "errorType": exc.__class__.__name__}

    storage = get_upload_persistence_readiness()
    checks["storage"] = {"status": "ready" if storage.get("ok") else "failed"}
    provider_check_name, provider_check = _generation_provider_readiness()
    checks[provider_check_name] = provider_check
    fatal = {
        name
        for name, check in checks.items()
        if check.get("status") == "failed"
        or (name == "openai" and settings.instant_html_enabled and check.get("canaryReady") is not True)
    }
    from fastapi import HTTPException

    if fatal:
        logger.warning("product_readiness_failed", extra={"fatalChecks": sorted(fatal)})
        raise HTTPException(status_code=503, detail="not_ready")
    logger.info("product_readiness_passed")
    return _coarse_health(True)


@router.get("/health/diagnostics")
def upload_diagnostics() -> dict:
    """Evaluate upload readiness while returning only coarse public status.

    Sanitized details are emitted to internal logs rather than the response.
    """
    readiness = get_upload_persistence_readiness()
    
    # Check database connectivity
    database_status = "unknown"
    database_error = None
    try:
        from app.db.session import get_engine

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        database_status = "connected"
    except Exception as exc:
        database_status = "failed"
        database_error = exc.__class__.__name__
    
    # Check storage backend
    storage_status = "unknown"
    storage_error = None
    try:
        storage = get_upload_storage()
        storage_status = "configured"
        storage_provider = storage.provider
    except Exception as exc:
        storage_status = "failed"
        storage_error = exc.__class__.__name__
        storage_provider = settings.upload_storage_backend
    
    ready = bool(readiness["ok"] and database_status == "connected" and storage_status == "configured")
    logger.info(
        "upload_diagnostics_evaluated",
        extra={
            "ready": ready,
            "databaseStatus": database_status,
            "storageStatus": storage_status,
            "databaseErrorType": database_error,
            "storageErrorType": storage_error,
        },
    )
    return _coarse_health(ready)


@router.get("/health/storage")
def storage_health(db: Session = Depends(get_db)) -> dict:
    required: dict[str, bool] = {}
    if settings.upload_storage_backend == "s3":
        required = {
            "bucket": bool(settings.upload_storage_s3_bucket),
            "region": bool(settings.upload_storage_s3_region),
            "accessKey": bool(settings.effective_s3_access_key),
            "secretKey": bool(settings.effective_s3_secret_key),
        }
    elif settings.upload_storage_backend == "supabase":
        required = {
            "url": bool(settings.supabase_url),
            "serviceRoleKey": bool(settings.supabase_service_role_key),
            "bucket": bool(settings.supabase_storage_bucket),
        }

    config_ok = all(required.values()) if required else settings.upload_storage_backend == "local"
    runtime_error = None
    try:
        storage = get_upload_storage()
        provider = storage.provider
    except Exception as exc:
        provider = settings.upload_storage_backend
        config_ok = False
        runtime_error = exc.__class__.__name__

    queue_counts = db.query(WorkflowJob.status, WorkflowJob.id).all()
    actionable_statuses = {JOB_STATUS_QUEUED, JOB_STATUS_FAILED_RETRYABLE}
    active_statuses = actionable_statuses | {JOB_STATUS_RUNNING}
    queue_depth = sum(1 for status, _job_id in queue_counts if str(status) in active_statuses)
    queued_count = sum(1 for status, _job_id in queue_counts if str(status) in actionable_statuses)

    logger.info(
        "storage_health_evaluated",
        extra={
            "ready": config_ok,
            "provider": provider,
            "activeQueueDepth": queue_depth,
            "queuedCount": queued_count,
            "runtimeErrorType": runtime_error,
        },
    )
    return _coarse_health(config_ok)


@router.get("/health/worker")
def worker_health(db: Session = Depends(get_db)) -> dict:
    actionable_statuses = {JOB_STATUS_QUEUED, JOB_STATUS_FAILED_RETRYABLE}
    active_statuses = actionable_statuses | {JOB_STATUS_RUNNING}
    queued_jobs = (
        db.query(WorkflowJob)
        .filter(WorkflowJob.status.in_(tuple(active_statuses)))
        .order_by(WorkflowJob.queued_at.asc().nullsfirst(), WorkflowJob.created_at.asc())
        .all()
    )
    queued_count = sum(1 for job in queued_jobs if str(job.status) in actionable_statuses)
    active_count = len(queued_jobs)
    oldest_queued = next((job for job in queued_jobs if str(job.status) in active_statuses), None)
    oldest_queued_age_seconds = None
    if oldest_queued is not None:
        anchor = oldest_queued.queued_at or oldest_queued.updated_at or oldest_queued.created_at
        if anchor is not None:
            if anchor.tzinfo is None:
                anchor = anchor.replace(tzinfo=timezone.utc)
            oldest_queued_age_seconds = max(0, int((datetime.now(timezone.utc) - anchor).total_seconds()))

    worker_required = active_count > 0 or queued_count > 0
    blocked = bool(oldest_queued_age_seconds is not None and oldest_queued_age_seconds > 300)

    logger.info(
        "worker_health_evaluated",
        extra={
            "ready": not blocked,
            "workerRequired": worker_required,
            "blocked": blocked,
            "activeCount": active_count,
            "queuedCount": queued_count,
            "oldestQueuedAgeSeconds": oldest_queued_age_seconds,
        },
    )
    return _coarse_health(not blocked)
