from __future__ import annotations

from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_DATABASE_URL, settings
from app.db.models import WorkflowJob
from app.services.storage.bucket_health import storage_pipeline_health_check
from app.services.storage.upload_readiness import get_upload_persistence_readiness
from app.services.admin.worker_health import get_latest_worker_heartbeat
from app.services.deck_processing.workflow_jobs import JOB_STATUS_COMPLETED, JOB_STATUS_FAILED_FINAL, JOB_STATUS_FAILED_RETRYABLE, JOB_STATUS_QUEUED, JOB_STATUS_RUNNING, JOB_STATUS_TIMED_OUT


def _check(status: str, ok: bool, message: str, details: dict | None = None) -> dict:
    return {"status": status, "ok": ok, "message": message, "details": details or {}}


def _database_check(db: Session) -> dict:
    try:
        value = db.execute(text("select 1")).scalar()
        return _check("ok", value == 1, "Database connection is reachable.", {"dialect": db.bind.dialect.name if db.bind else None})
    except Exception as exc:
        return _check("failed", False, "Database connection failed.", {"errorType": exc.__class__.__name__, "error": str(exc)[:300]})


def _storage_check() -> dict:
    try:
        result = storage_pipeline_health_check()
        return _check("ok" if result.get("ok") else "failed", bool(result.get("ok")), "Storage pipeline health check completed.", result)
    except Exception as exc:
        return _check("failed", False, "Storage pipeline health check failed.", {"errorType": exc.__class__.__name__, "error": str(exc)[:300]})


def _upload_persistence_check() -> dict:
    result = get_upload_persistence_readiness()
    return _check(
        "ok" if result.get("ok") else "failed",
        bool(result.get("ok")),
        "Upload persistence settings are ready." if result.get("ok") else "Upload persistence settings need attention.",
        result,
    )


def _required_env_check() -> dict:
    problems: list[str] = []
    if not settings.is_production:
        problems.append("APP_ENV/RAILWAY_ENVIRONMENT is not production")
    if settings.database_url == DEFAULT_DATABASE_URL or "localhost" in settings.database_url:
        problems.append("database URL still points to local/default database")
    if settings.upload_storage_backend == "local" and settings.is_production:
        problems.append("production storage backend is local")
    if settings.upload_storage_backend == "s3":
        if not settings.upload_storage_s3_bucket:
            problems.append("storage bucket missing")
        if not settings.upload_storage_s3_region:
            problems.append("storage region missing")
        if settings.upload_storage_s3_provider == "compatible" and not settings.upload_storage_s3_endpoint_url:
            problems.append("storage endpoint missing")
        if not settings.effective_s3_access_key:
            problems.append("storage access key missing")
        if not settings.effective_s3_secret_key:
            problems.append("storage credential missing")
    if not settings.upload_security_scan_command:
        problems.append("upload security scan command missing")
    return _check(
        "ok" if not problems else "failed",
        not problems,
        "Required production settings are present." if not problems else "Required production settings need attention.",
        {
            "appEnv": settings.app_env,
            "railwayEnvironment": settings.railway_environment,
            "appRole": settings.app_role,
            "storageBackend": settings.upload_storage_backend,
            "problems": problems,
        },
    )


def _ai_provider_check() -> dict:
    from app.services.llm.qwen_strategy import get_qwen_health_summary
    from app.services.llm.dashscope_provider import get_last_error_category, get_last_success_at
    from app.services.llm.embedding_service import get_embedding_metrics, get_embedding_provider_status

    configured = {
        "openai": bool(settings.openai_api_key),
        "openrouter": bool(settings.openrouter_api_key),
        "anthropic": bool(settings.anthropic_api_key),
        "dashscope": bool(settings.effective_qwen_api_key),
    }
    generation_mode = settings.deck_generation_mode.strip().lower()
    required_provider = "dashscope" if generation_mode in {"qwen", "dashscope"} else generation_mode
    provider_supported = required_provider in configured
    ok = bool(provider_supported and configured[required_provider])
    access_status = "configured_unverified" if ok else "not_configured"
    qwen_health = get_qwen_health_summary()
    return _check(
        access_status if ok else "warning",
        False if required_provider == "openai" else ok,
        f"Required AI provider {required_provider} is configured but access is unverified."
        if ok
        else f"Required AI provider {required_provider} is not configured.",
        {
            "configured": configured,
            "generationMode": generation_mode,
            "requiredProvider": required_provider,
            "accessStatus": access_status,
            "qwen": {
                **qwen_health,
                "last_error_category": get_last_error_category(),
                "last_success_at": get_last_success_at(),
            },
            "embedding": {
                **get_embedding_provider_status(),
                "metrics": get_embedding_metrics(),
            },
        },
    )


def _cors_check() -> dict:
    origins = settings.cors_origins
    production_origin_present = any("deck.aistack.codes" in origin for origin in origins)
    ok = bool(origins) and (production_origin_present or not settings.is_production)
    return _check(
        "ok" if ok else "warning",
        ok,
        "CORS origins look usable." if ok else "Production frontend origin may be missing from CORS origins.",
        {"origins": origins},
    )


def _queue_check(db: Session) -> dict:
    try:
        queued = db.query(WorkflowJob).filter(WorkflowJob.status.in_((JOB_STATUS_QUEUED, JOB_STATUS_FAILED_RETRYABLE))).count()
        running = db.query(WorkflowJob).filter(WorkflowJob.status == JOB_STATUS_RUNNING).count()
        completed = db.query(WorkflowJob).filter(WorkflowJob.status == JOB_STATUS_COMPLETED).count()
        failed = db.query(WorkflowJob).filter(WorkflowJob.status.in_((JOB_STATUS_FAILED_FINAL, JOB_STATUS_TIMED_OUT))).count()
        return _check(
            "ok",
            True,
            "Workflow job queue table is readable.",
            {"queued": queued, "running": running, "completed": completed, "failedOrManualReview": failed},
        )
    except Exception as exc:
        return _check("failed", False, "Workflow job queue table is not readable.", {"errorType": exc.__class__.__name__, "error": str(exc)[:300]})


def _worker_check(db: Session) -> dict:
    heartbeat = get_latest_worker_heartbeat(db)
    status = heartbeat.get("status")
    ok = bool(heartbeat.get("ok"))
    if status == "missing":
        return _check("warning", False, "Worker has not recorded a heartbeat yet.", heartbeat)
    if status == "stale":
        return _check("warning", False, "Worker heartbeat is stale.", heartbeat)
    return _check("ok" if ok else "warning", ok, str(heartbeat.get("message") or "Worker heartbeat check complete."), heartbeat)


def get_deployment_readiness(db: Session) -> dict:
    checked_at = datetime.utcnow()
    checks = {
        "database": _database_check(db),
        "requiredEnv": _required_env_check(),
        "uploadPersistence": _upload_persistence_check(),
        "storage": _storage_check(),
        "aiProvider": _ai_provider_check(),
        "cors": _cors_check(),
        "workerQueue": _queue_check(db),
        "workerHeartbeat": _worker_check(db),
    }
    # Production readiness must fail closed when generation or worker execution
    # is unavailable. Non-production diagnostics keep those checks advisory so
    # local contract fixtures can run without real provider credentials.
    required_keys = {"database", "requiredEnv", "uploadPersistence", "storage", "workerQueue"}
    if settings.is_production:
        required_keys.update({"aiProvider", "workerHeartbeat"})
    hard_ok = all(checks[key]["ok"] for key in required_keys)
    warning_count = sum(1 for check in checks.values() if check["status"] == "warning")
    failed_count = sum(1 for check in checks.values() if check["status"] == "failed")
    return {
        "ok": hard_ok and failed_count == 0,
        "status": "ok" if hard_ok and failed_count == 0 and warning_count == 0 else "warning" if hard_ok else "failed",
        "environment": settings.app_env,
        "serviceRole": settings.app_role,
        "checkedAt": checked_at.isoformat(),
        "checks": checks,
        "summary": {
            "hardOk": hard_ok,
            "warningCount": warning_count,
            "failedCount": failed_count,
            "readyForTesterTraffic": hard_ok and failed_count == 0,
            "nextDeploymentCheckAt": (checked_at + timedelta(minutes=10)).isoformat(),
        },
    }
