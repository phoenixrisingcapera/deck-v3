"""
Deck Processing Worker - Background job processor for workflow jobs.

CRITICAL PATH: Worker polls queue → Claims job → Processes → Updates status

This file is the main worker entrypoint that runs as a separate Railway service.
It processes all asynchronous deck processing tasks:
- Source ingestion (PDF/PPTX parsing)
- Source extraction (slide extraction, thumbnail generation)
- Brand extraction (website/logo analysis)
- Smart Deck context (LLM context building)
- LLM generation (slide generation)
- Schema validation (output validation)
- Preview render (slide image generation)
- Apply version (final deck assembly)
- Export (PPTX/PDF export)

WORKER LIFECYCLE:
1. Worker starts (Railway service or local script)
2. Worker connects to database
3. Worker enters polling loop:
   a. Query workflow_jobs for queued jobs
   b. Claim job (optimistic locking):
      - UPDATE workflow_jobs SET status='running', locked_by=worker_id
      - WHERE id=job_id AND status='queued'
   c. If job claimed:
      - Process job based on job_type
      - Update job status to 'completed' or 'failed'
      - Record heartbeat
   d. If no job claimed:
      - Sleep for 10 seconds
      - Repeat
4. Worker records heartbeat every 30 seconds
5. Worker handles graceful shutdown on SIGTERM/SIGINT

OPTIMISTIC LOCKING:
- Multiple workers can run simultaneously
- Each worker tries to claim a job
- Only one worker succeeds (database constraint)
- Prevents duplicate processing

HEARTBEAT:
- Worker records heartbeat every 30 seconds
- Heartbeat includes: worker_id, status, last_claimed_job_id
- Admin dashboard checks heartbeat for health monitoring
- Stale heartbeat (>5 minutes) indicates worker is stuck

JOB TYPES:
- source_ingestion: Parse uploaded PDF/PPTX
- source_extraction: Extract slides, generate thumbnails
- brand_extraction: Analyze website/logo, build brand profile
- smart_deck_context: Build LLM context from deck + brand
- llm_generation: Generate Smart Deck slides with LLM
- schema_validation: Validate generated slide structure
- preview_render: Generate slide preview images
- apply_version: Assemble final deck
- export: Export to PPTX/PDF

ERROR HANDLING:
- Job failures are recorded in workflow_jobs table
- Failed jobs can be retried (max_attempts: 2)
- Stale jobs are recovered by stale_job_rescuer worker
- All errors are logged for debugging

HEALTH CHECK:
- Worker serves HTTP health check on PORT (default 8080)
- GET /api/health returns worker status
- Railway uses this for health monitoring
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)


def _apply_storage_env_aliases() -> None:
    aliases = {
        "BUCKET": "RAILWAY_BUCKET_NAME",
        "REGION": "RAILWAY_BUCKET_REGION",
        "ENDPOINT": "RAILWAY_BUCKET_ENDPOINT",
        "ACCESS_" + "KEY_ID": "RAILWAY_BUCKET_" + "ACCESS_KEY",
        "SECRET_" + "ACCESS_KEY": "RAILWAY_BUCKET_" + "SECRET_KEY",
    }
    for source, target in aliases.items():
        value = os.getenv(source)
        if value and not os.getenv(target):
            os.environ[target] = value


_apply_storage_env_aliases()
os.environ.setdefault("UPLOAD_SECURITY_SCAN_COMMAND", "disabled")

from app.core.worker_startup_policy import apply_worker_identity_defaults, validate_worker_environment_before_import

# Identity defaults and security validation must complete before importing
# settings, database engines, queue handlers, or provider-bearing modules.
apply_worker_identity_defaults()
WORKER_IDENTITY = validate_worker_environment_before_import(allow_health_only=True)
AUDIT_HEALTH_ONLY = WORKER_IDENTITY.health_only

if not AUDIT_HEALTH_ONLY:
    from app.db.session import SessionLocal
    from app.workers.dispatch.worker_runtime_service import (
        configured_worker_job_types,
        generic_generation_pipeline_worker_enabled,
        infer_worker_kind_from_service_name,
        inferred_generic_service_name,
        process_next_durable_deck,
        recover_stale_processing_runs,
        worker_recovery_only,
    )
    from app.services.admin.worker_health import record_worker_heartbeat

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("deck_processing_worker")

DEFAULT_IDLE_SLEEP_SECONDS = float(os.getenv("DECK_WORKER_POLL_INTERVAL_SECONDS", "10"))
HEARTBEAT_INTERVAL_SECONDS = float(os.getenv("DECK_WORKER_HEARTBEAT_INTERVAL_SECONDS", "30"))
WORKER_ID = os.getenv("DECK_WORKER_ID") or f"{socket.gethostname()}:{os.getpid()}"
LAST_HEARTBEAT_AT = 0.0
LAST_CLAIMED_RUN_ID: str | None = None
LAST_STATUS = "starting"
LAST_ERROR: str | None = None
HEALTH_STATE_LOCK = threading.Lock()
HEALTH_READY = False
LAST_RELEASE_RECONCILIATION_AT = 0.0
RELEASE_RECONCILIATION_INTERVAL_SECONDS = 30.0


def _mark_worker_not_ready(*, event: str, error_type: str | None = None) -> None:
    global HEALTH_READY
    with HEALTH_STATE_LOCK:
        HEALTH_READY = False
    logger.warning("worker_not_ready", extra={"healthEvent": event, "errorType": error_type})


def _mark_worker_ready() -> None:
    global HEALTH_READY
    if not AUDIT_HEALTH_ONLY:
        with HEALTH_STATE_LOCK:
            HEALTH_READY = True


def worker_health_status() -> tuple[int, dict[str, str]]:
    with HEALTH_STATE_LOCK:
        ready = HEALTH_READY and not AUDIT_HEALTH_ONLY
    return (200, {"status": "ready"}) if ready else (503, {"status": "not_ready"})


def worker_health_payload() -> dict[str, str]:
    """Public worker health is intentionally coarse and identifier-free."""
    return worker_health_status()[1]


def _instant_provider_role(*, configured_job_types_csv: str | None = None) -> bool:
    if AUDIT_HEALTH_ONLY:
        return False
    if configured_job_types_csv is not None:
        return "instant_deck_generation" in {
            value.strip() for value in configured_job_types_csv.split(",") if value.strip()
        }
    return "instant_deck_generation" in configured_worker_job_types()


def _refresh_instant_provider_attestation(
    *, force: bool = False, configured_job_types_csv: str | None = None,
) -> bool | None:
    """Own canonical Instant readiness before health or queue claim."""
    if not _instant_provider_role(configured_job_types_csv=configured_job_types_csv):
        return None
    from app.core.config import settings
    from app.services.llm.openai_provider import (
        fail_instant_openai_model_access_attestation,
        refresh_instant_openai_model_access_attestation,
    )

    try:
        return refresh_instant_openai_model_access_attestation(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            force=force,
        )
    except Exception as exc:
        return fail_instant_openai_model_access_attestation(exc)


def _expected_heads(config_path: str) -> tuple[str, ...]:
    config = AlembicConfig(config_path)
    return tuple(ScriptDirectory.from_config(config).get_heads())


def _migration_heads(connection, table_name: str) -> tuple[str, ...]:
    return tuple(connection.execute(text(f"SELECT version_num FROM {table_name} ORDER BY version_num")).scalars())


def _queue_tables_ready(connection) -> bool:
    required_tables = (
        "workflow_jobs",
        "workflow_job_dependencies",
        "workflow_job_events",
        "workflow_job_artifacts",
    )
    if connection.dialect.name == "sqlite":
        present_tables = set(inspect(connection).get_table_names())
        return set(required_tables).issubset(present_tables)

    for table_name in required_tables:
        present = connection.execute(text("SELECT to_regclass(:table_name)"), {"table_name": f"public.{table_name}"}).scalar_one_or_none()
        if present != table_name:
            return False
    return True


def _worker_startup_preflight(*, configured_job_types: str, recovery_only: bool) -> None:
    from app.core.config import settings
    from app.db.session import get_ai_engine, get_engine
    from app.services.storage.upload_readiness import get_worker_upload_persistence_readiness

    with get_engine().connect() as connection:
        connection.execute(text("SELECT 1"))
        current_core_heads = _migration_heads(connection, "alembic_version_core")
        expected_core_heads = _expected_heads("alembic.ini")
        if set(current_core_heads) != set(expected_core_heads):
            raise RuntimeError("Core database migration head is not current")
        if not _queue_tables_ready(connection):
            raise RuntimeError("Workflow queue tables are unavailable")

    if settings.ai_database_url:
        with get_ai_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
            current_ai_heads = _migration_heads(connection, "alembic_version_ai")
            expected_ai_heads = _expected_heads("alembic_ai.ini")
            if set(current_ai_heads) != set(expected_ai_heads):
                raise RuntimeError("AI database migration head is not current")
            vector_extension = connection.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))\
                .scalar_one_or_none()
            if vector_extension != "vector":
                raise RuntimeError("AI database pgvector extension is unavailable")
            vector_dimension = connection.execute(
                text(
                    "SELECT format_type(a.atttypid, a.atttypmod) FROM pg_attribute a "
                    "JOIN pg_class c ON c.oid = a.attrelid "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = 'public' AND c.relname = 'vector_chunks' "
                    "AND a.attname = 'embedding' AND a.attnum > 0 AND NOT a.attisdropped"
                )
            ).scalar_one_or_none()
            if vector_dimension != f"vector({int(settings.embedding_dimensions)})":
                raise RuntimeError("AI database embedding vector dimension is invalid")

    storage_readiness = get_worker_upload_persistence_readiness(
        require_workspace_ai=WORKER_IDENTITY.provider_capable,
    )
    if not storage_readiness.get("ok"):
        raise RuntimeError("Upload persistence is not ready for worker startup")


class _WorkerHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path not in {"/api/health", "/api/health/product-ready", "/health"}:
            self.send_response(404)
            self.end_headers()
            return
        status_code, payload = worker_health_status()
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def _record_heartbeat(
    *,
    force: bool = False,
    status: str = "alive",
    last_error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    global LAST_HEARTBEAT_AT, LAST_STATUS, LAST_ERROR
    LAST_STATUS = status
    LAST_ERROR = last_error
    now = time.monotonic()
    if not force and now - LAST_HEARTBEAT_AT < HEARTBEAT_INTERVAL_SECONDS:
        return True

    try:
        record_worker_heartbeat(
            worker_id=WORKER_ID,
            status=status,
            last_claimed_run_id=LAST_CLAIMED_RUN_ID,
            last_error=last_error,
            metadata={
                "pollIntervalSeconds": DEFAULT_IDLE_SLEEP_SECONDS,
                "entrypoint": "scripts/deck_processing_worker.py",
                **(metadata or {}),
            },
            commit=True,
        )
        LAST_HEARTBEAT_AT = now
        return True
    except Exception as exc:
        logger.exception("deck_worker_heartbeat_failed", extra={"worker_id": WORKER_ID})
        return False


def _recover_stale_runs() -> dict[str, Any]:
    db = None
    try:
        db = SessionLocal()
        result = recover_stale_processing_runs(db, worker_id=WORKER_ID)
        from app.services.llm.instant_html_operation_service import (
            purge_expired_raw_artifacts,
            reconcile_artifact_cleanup_tasks,
            reconcile_charging_operations,
            reconcile_enqueue_pending_operations,
            reconcile_release_pending_operations,
        )

        result["instantHtmlChargeReconciled"] = reconcile_charging_operations(db)
        result["instantHtmlEnqueueReconciled"] = reconcile_enqueue_pending_operations(db)
        result["instantHtmlReleaseReconciled"] = reconcile_release_pending_operations(db)
        result["instantHtmlArtifactCleanupReconciled"] = reconcile_artifact_cleanup_tasks(
            db, worker_id=WORKER_ID, limit=25
        )
        result["instantHtmlRawPurged"] = purge_expired_raw_artifacts(db)
        return result
    except Exception:
        logger.exception("deck_worker_stale_recovery_failed", extra={"worker_id": WORKER_ID})
        raise
    finally:
        if db is not None:
            db.close()


def _reconcile_deferred_instant_releases(
    *, configured_job_types_csv: str, force: bool = False,
) -> int | None:
    """Release failed Instant Deck reservations on the live Railway worker.

    Preview rendering deliberately defers this billing mutation. Minimal
    deployments have no separate stale-job rescuer, so the provider-capable
    Instant Deck worker owns this bounded idempotent maintenance tick.
    """
    global LAST_RELEASE_RECONCILIATION_AT
    if not _instant_provider_role(configured_job_types_csv=configured_job_types_csv):
        return None
    now = time.monotonic()
    if (
        not force
        and now - LAST_RELEASE_RECONCILIATION_AT < RELEASE_RECONCILIATION_INTERVAL_SECONDS
    ):
        return None
    LAST_RELEASE_RECONCILIATION_AT = now
    db = SessionLocal()
    try:
        from app.services.llm.instant_html_operation_service import (
            reconcile_release_pending_operations,
        )

        reconciled = reconcile_release_pending_operations(db)
        if reconciled:
            logger.info(
                "instant_deck_release_pending_reconciled",
                extra={"worker_id": WORKER_ID, "reconciled": reconciled},
            )
        return reconciled
    except Exception:
        logger.exception(
            "instant_deck_release_pending_reconciliation_failed",
            extra={"worker_id": WORKER_ID},
        )
        return 0
    finally:
        db.close()


def _startup_readiness_check(*, configured_job_types: str, recovery_only: bool) -> bool | None:
    startup_attested = _refresh_instant_provider_attestation(force=True)
    metadata = {
        "configuredJobTypes": configured_job_types,
        "recoveryOnly": recovery_only,
        "instantProviderAttested": startup_attested,
    }
    if startup_attested is False:
        _mark_worker_not_ready(event="instant_provider_attestation")
    db = None
    try:
        _worker_startup_preflight(configured_job_types=configured_job_types, recovery_only=recovery_only)
        if startup_attested is True and _instant_provider_role(configured_job_types_csv=configured_job_types):
            # Prepare stable reusable guidance before any customer job is
            # claimed. This call owns only an AI-database session and closes it
            # before/after provider I/O; no core workflow transaction is held.
            from app.services.llm.deck_chunking_service import sync_instant_deck_knowledge_chunks

            knowledge_index = sync_instant_deck_knowledge_chunks()
            metadata["instantKnowledgeIndexStatus"] = str(knowledge_index.get("status") or "unknown")
            metadata["instantKnowledgeChunkCount"] = int(knowledge_index.get("chunkCount") or 0)
            if knowledge_index.get("status") != "ready" or int(knowledge_index.get("chunkCount") or 0) <= 0:
                raise RuntimeError("Instant Deck stable knowledge index is not ready")
        db = SessionLocal()
        db.connection()
        if not _record_heartbeat(force=True, status="started", metadata=metadata):
            _mark_worker_not_ready(event="startup_heartbeat")
            return startup_attested
        if startup_attested is not False:
            _mark_worker_ready()
        return startup_attested
    except Exception as exc:
        _mark_worker_not_ready(event="startup_readiness", error_type=exc.__class__.__name__)
        _record_heartbeat(force=True, status="error", last_error="startup_readiness_failed", metadata=metadata)
        raise
    finally:
        if db is not None:
            db.close()


def run_once(*, configured_job_types: str | None = None, recovery_only: bool = False) -> bool:
    global LAST_CLAIMED_RUN_ID

    if recovery_only:
        try:
            recovery = _recover_stale_runs()
        except Exception as exc:
            _mark_worker_not_ready(event="recovery", error_type=exc.__class__.__name__)
            _record_heartbeat(force=True, status="error", last_error="recovery_failed")
            return False
        _record_heartbeat(
            force=True,
            status="recovery",
            metadata={
                "configuredJobTypes": configured_job_types,
                "recoveryOnly": True,
                "recovered": recovery.get("recovered", 0),
                "timedOut": recovery.get("timedOut", 0),
            },
        )
        logger.info(
            "deck_worker_stale_recovery_cycle",
            extra={"worker_id": WORKER_ID, **recovery},
        )
        _mark_worker_ready()
        return False

    _reconcile_deferred_instant_releases(
        configured_job_types_csv=str(configured_job_types or ""),
    )
    instant_attested = _refresh_instant_provider_attestation(
        configured_job_types_csv=configured_job_types
    )
    if instant_attested is False:
        # Missing/transient provider readiness is process readiness, not a
        # customer-operation failure. Keep the process unready for Instant,
        # but let the dispatcher filter only Instant claims so mixed-role
        # workers can continue provider-free work.
        _mark_worker_not_ready(event="instant_provider_attestation")
        _record_heartbeat(
            status="not_ready",
            last_error="instant_provider_attestation_unavailable",
            metadata={"configuredJobTypes": configured_job_types},
        )

    db = None
    try:
        db = SessionLocal()
        if instant_attested is None:
            result = process_next_durable_deck(db, worker_id=WORKER_ID)
        else:
            result = process_next_durable_deck(
                db,
                worker_id=WORKER_ID,
                instant_claims_enabled=instant_attested,
            )
        if result is None:
            _record_heartbeat(
                status="idle",
                metadata={"configuredJobTypes": configured_job_types},
            )
            if instant_attested is not False:
                _mark_worker_ready()
            return False

        LAST_CLAIMED_RUN_ID = str(result.get("id") or "") or LAST_CLAIMED_RUN_ID
        _record_heartbeat(
            force=True,
            status="processed",
            metadata={"configuredJobTypes": configured_job_types},
        )
        if instant_attested is not False:
            _mark_worker_ready()
        logger.info(
            "deck_worker_processed_job",
            extra={
                "processing_run_id": result.get("id"),
                "deck_id": result.get("deckId"),
                "status": result.get("status"),
                "stage": result.get("stage"),
                "worker_id": WORKER_ID,
            },
        )
        print(
            f"processed {result.get('id')} deck={result.get('deckId')} status={result.get('status')}",
            flush=True,
        )
        return True
    except Exception as exc:
        _mark_worker_not_ready(event="worker_cycle", error_type=exc.__class__.__name__)
        _record_heartbeat(
            force=True,
            status="error",
            last_error="core_database_failed" if exc.__class__.__module__.startswith("sqlalchemy.") else "worker_cycle_failed",
            metadata={"configuredJobTypes": configured_job_types},
        )
        logger.exception("deck_worker_job_failed", extra={"worker_id": WORKER_ID})
        return False
    finally:
        if db is not None:
            db.close()


def run_worker(
    *,
    once: bool = False,
    idle_sleep_seconds: float = DEFAULT_IDLE_SLEEP_SECONDS,
    stop_event: threading.Event | None = None,
    ) -> None:
    stop_event = stop_event or threading.Event()
    configured_job_types = ",".join(sorted(configured_worker_job_types()))
    recovery_only = worker_recovery_only()
    _startup_readiness_check(configured_job_types=configured_job_types, recovery_only=recovery_only)
    if not recovery_only:
        # A provider/runtime crash can leave a durable job in ``running`` until
        # its lease expires.  The production vertical-slice worker may be the
        # only worker process, so reclaim expired leases once before the normal
        # claim loop starts.  This uses the same bounded, audited recovery path
        # as the dedicated recovery role and never touches a live lease.
        startup_recovery = _recover_stale_runs()
        logger.info(
            "deck_worker_startup_stale_recovery",
            extra={"worker_id": WORKER_ID, **startup_recovery},
        )
        _reconcile_deferred_instant_releases(
            configured_job_types_csv=configured_job_types,
            force=True,
        )

    while not stop_event.is_set():
        processed = run_once(configured_job_types=configured_job_types, recovery_only=recovery_only)
        if once:
            return
        if not processed:
            stop_event.wait(idle_sleep_seconds)

    _record_heartbeat(force=True, status="stopped", metadata={"configuredJobTypes": configured_job_types})


def _serve_healthcheck(port: int, stop_event: threading.Event) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), _WorkerHealthHandler)
    server.timeout = 1.0

    def _shutdown_when_stopped() -> None:
        stop_event.wait()
        server.shutdown()

    threading.Thread(target=_shutdown_when_stopped, daemon=True).start()
    try:
        server.serve_forever(poll_interval=1.0)
    finally:
        server.server_close()


def _run_audit_health_only() -> None:
    _mark_worker_not_ready(event="audit_health_only")
    logger.warning(
        "worker_audit_health_only",
        extra={
            "violationCount": len(WORKER_IDENTITY.violations),
            "forbiddenVariableNames": list(WORKER_IDENTITY.forbidden_names),
        },
    )
    stop_event = threading.Event()

    def _handle_signal(_signum: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    _serve_healthcheck(int(os.environ.get("PORT", "8080")), stop_event)


def _apply_worker_role_defaults() -> None:
    """Derive worker env defaults from Railway service naming.

    Generic legacy worker service names must either run recovery-only or opt in
    explicitly to the multi-stage Smart Deck generation pipeline.
    """
    apply_worker_identity_defaults()
    app_role = os.getenv("APP_ROLE", "worker").strip().lower().replace("-", "_")
    service_name = str(os.getenv("RAILWAY_SERVICE_NAME") or "").strip().lower()
    generic_service_name = inferred_generic_service_name()
    if not os.getenv("WORKER_KIND"):
        if app_role.startswith("worker_"):
            os.environ["WORKER_KIND"] = app_role.removeprefix("worker_")
        elif app_role == "worker":
            default_kind = os.getenv("DECK_WORKER_KIND")
            if default_kind:
                os.environ["WORKER_KIND"] = default_kind.strip().lower().replace("-", "_")
            else:
                if os.getenv("DECK_WORKER_JOB_TYPES"):
                    return
                inferred_kind = infer_worker_kind_from_service_name(os.getenv("RAILWAY_SERVICE_NAME"))
                if inferred_kind:
                    os.environ["WORKER_KIND"] = inferred_kind
    if app_role == "stale_job_rescuer":
        os.environ.setdefault("DECK_WORKER_RECOVERY_ONLY", "true")
    if os.getenv("WORKER_KIND") == "stale_job_rescuer":
        os.environ.setdefault("DECK_WORKER_RECOVERY_ONLY", "true")
    if not os.getenv("DECK_WORKER_JOB_TYPES") and os.getenv("WORKER_KIND") and os.getenv("WORKER_KIND") != "stale_job_rescuer":
        os.environ["DECK_WORKER_JOB_TYPES"] = os.getenv("WORKER_KIND", "")


def _ensure_worker_role_contract() -> None:
    """Fail fast when Railway role inference would strand queued generation jobs."""
    generic_service_name = inferred_generic_service_name()
    if not generic_service_name:
        return
    if worker_recovery_only() and not generic_generation_pipeline_worker_enabled():
        return
    if generic_generation_pipeline_worker_enabled():
        return
    raise RuntimeError(
        "Legacy generic worker service name inferred a non-recovery worker without an explicit job-type contract. "
        "Either run recovery-only, rename the Railway service to a dedicated worker-*, or set "
        "DECK_ENABLE_GENERIC_GENERATION_PIPELINE_WORKER=true to claim llm_generation,schema_validation,preview_render,db_publisher."
    )


def _ensure_legacy_worker_disabled_in_production(*, recovery_only: bool) -> None:
    app_env = str(os.getenv("APP_ENV") or "").strip().lower()
    service_name = str(os.getenv("RAILWAY_SERVICE_NAME") or "").strip().lower()
    if app_env != "production":
        return
    if service_name in {"deck-processing-worker", "deck-processing-worker-service"}:
        if generic_generation_pipeline_worker_enabled():
            return
        if recovery_only:
            return
        raise RuntimeError(
            "Legacy deck-processing-worker is disabled in production. "
            "Use a dedicated worker-* service, the recovery-only stale-job rescuer, or explicitly opt into "
            "DECK_ENABLE_GENERIC_GENERATION_PIPELINE_WORKER=true for the Smart Deck generation pipeline."
        )


def main() -> None:
    if AUDIT_HEALTH_ONLY:
        _run_audit_health_only()
        return
    _apply_worker_role_defaults()
    from app.workers.render_role_security import validate_render_worker_secret_contract

    validate_render_worker_secret_contract()
    parser = argparse.ArgumentParser(description="Process durable DeckAiStack workflow jobs.")
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit.")
    parser.add_argument(
        "--idle-sleep-seconds",
        type=float,
        default=DEFAULT_IDLE_SLEEP_SECONDS,
        help="Sleep duration when no queued jobs are available.",
    )
    args = parser.parse_args()
    _ensure_worker_role_contract()
    _ensure_legacy_worker_disabled_in_production(recovery_only=worker_recovery_only())

    if args.once:
        run_worker(once=True, idle_sleep_seconds=args.idle_sleep_seconds)
        return

    stop_event = threading.Event()
    failure: dict[str, str] = {}

    def _handle_signal(_signum: int, _frame: object) -> None:
        logger.info("deck_worker_stop_requested", extra={"signal": _signum, "worker_id": WORKER_ID})
        stop_event.set()

    def _worker_loop() -> None:
        try:
            run_worker(once=False, idle_sleep_seconds=args.idle_sleep_seconds, stop_event=stop_event)
        except BaseException:  # pragma: no cover - defensive, surfaces worker crash to Railway
            failure["traceback"] = traceback.format_exc()
            stop_event.set()
            raise

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    worker_thread = threading.Thread(target=_worker_loop, name="deck-processing-worker", daemon=True)
    worker_thread.start()

    logger.info(
        "deck_worker_started",
        extra={
            "poll_interval_seconds": args.idle_sleep_seconds,
            "worker_id": WORKER_ID,
            "health_port": int(os.environ.get("PORT", "8080")),
        },
    )

    try:
        _serve_healthcheck(int(os.environ.get("PORT", "8080")), stop_event)
    finally:
        stop_event.set()
        worker_thread.join(timeout=5.0)
        if failure.get("traceback"):
            print(failure["traceback"], flush=True)
            raise SystemExit(1)
        logger.info("deck_worker_stopped", extra={"worker_id": WORKER_ID})


if __name__ == "__main__":
    main()
