from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from app.core.railway_env import apply_railway_env_aliases
from app.core.worker_startup_policy import SERVICE_WORKER_KINDS, normalize_name
from app.core.instant_html_renderer_security import (
    is_instant_html_renderer_role,
    validate_instant_html_renderer_environment,
)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = "8080"


def _truthy(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_railway() -> bool:
    return any(
        os.getenv(name)
        for name in (
            "RAILWAY_ENVIRONMENT",
            "RAILWAY_ENVIRONMENT_ID",
            "RAILWAY_SERVICE_NAME",
            "RAILWAY_PROJECT_ID",
        )
    )


def _prepare_runtime_defaults() -> None:
    """Set safe runtime defaults required before importing app settings.

    The current upload path validates file extension, MIME type, and upload size in
    Python before persistence. A scanner command is not invoked by the active upload
    service, but older production settings still require the variable to exist. Set
    a harmless sentinel here so Railway deployments do not fail startup because of
    an unused scanner knob.
    """

    os.environ.setdefault("UPLOAD_SECURITY_SCAN_COMMAND", "disabled")
    apply_railway_env_aliases()


def _run_runtime_schema_bootstrap(migration_env: dict[str, str]) -> None:
    # DISABLED: runtime table creation is replaced by independent Alembic jobs.
    print("Skipping legacy runtime schema bootstrap; migrations own schema changes.", flush=True)


def _run_migrations_if_enabled() -> None:
    # Railway pre-deploy owns schema migration. This guard is intentionally
    # application-level because a service-level start-command override can
    # bypass railway.toml and otherwise race the pre-deploy migration.
    app_role = os.getenv("APP_ROLE", "api").strip().lower()
    if _is_railway() and app_role not in {"migration", "core-migration", "ai-migration"}:
        print("Skipping service startup migrations; Railway pre-deploy owns Alembic.", flush=True)
        return

    default_run_migrations = True
    if not _truthy(os.getenv("RUN_MIGRATIONS_ON_STARTUP"), default=default_run_migrations):
        print("Skipping schema bootstrap because RUN_MIGRATIONS_ON_STARTUP is false.", flush=True)
        return

    migration_env = {**os.environ, "APP_ROLE": "migration"}
    run_alembic = _truthy(
        os.getenv("RUN_ALEMBIC_MIGRATIONS_ON_STARTUP"),
        default=True,
    )

    if not run_alembic:
        print(
            "Skipping Alembic on Railway startup; running runtime schema bootstrap only.",
            flush=True,
        )
        allow_migration_failure = _truthy(
            os.getenv("ALLOW_MIGRATION_FAILURE_ON_STARTUP"),
            default=False,
        )
        try:
            _run_runtime_schema_bootstrap(migration_env)
        except subprocess.CalledProcessError as exc:
            if not allow_migration_failure:
                raise
            print(
                "WARNING: Runtime schema bootstrap failed during Railway startup. "
                "Continuing so the API/worker can start and expose health diagnostics. "
                f"Exit code: {exc.returncode}",
                flush=True,
            )
        return

    print("Running Alembic migrations before starting service.", flush=True)
    allow_migration_failure = _truthy(
        os.getenv("ALLOW_MIGRATION_FAILURE_ON_STARTUP"),
        default=False,
    )

    try:
        core_migration_env = {**migration_env, "APP_ROLE": "core-migration"}
        subprocess.check_call([sys.executable, "-m", "alembic", "upgrade", "heads"], env=core_migration_env)
    except subprocess.CalledProcessError as exc:
        if not allow_migration_failure:
            raise
        print(
            "WARNING: Alembic upgrade failed during Railway startup. "
            "Running runtime schema bootstrap and continuing so the API can start. "
            f"Exit code: {exc.returncode}",
            flush=True,
        )

    # Run AI database migrations if AI_DATABASE_URL is configured
    from app.core.config import settings
    if settings.ai_database_url:
        print("Running AI database migrations.", flush=True)
        try:
            ai_migration_env = {**migration_env, "APP_ROLE": "ai-migration"}
            subprocess.check_call(
                [sys.executable, "-m", "alembic", "-c", "alembic_ai.ini", "upgrade", "heads"],
                env=ai_migration_env,
            )
        except subprocess.CalledProcessError as exc:
            if not allow_migration_failure:
                raise
            print(
                "WARNING: AI database Alembic upgrade failed during Railway startup. "
                "Continuing so the API can start. "
                f"Exit code: {exc.returncode}",
                flush=True,
            )

    try:
        _run_runtime_schema_bootstrap(migration_env)
    except subprocess.CalledProcessError as exc:
        if not allow_migration_failure:
            raise
        print(
            "WARNING: Runtime schema bootstrap failed after Alembic during Railway startup. "
            "Continuing so the API/worker can start and expose health diagnostics. "
            f"Exit code: {exc.returncode}",
            flush=True,
        )


def _exec_api() -> None:
    port = os.getenv("PORT", DEFAULT_PORT)
    host = os.getenv("HOST", DEFAULT_HOST)
    print(f"Starting API on {host}:{port}.", flush=True)
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            port,
        ],
    )


def _exec_instant_html_renderer() -> None:
    port = os.getenv("PORT", DEFAULT_PORT)
    host = os.getenv("HOST", DEFAULT_HOST)
    validate_instant_html_renderer_environment()
    print(f"Starting dedicated Instant HTML renderer on {host}:{port}.", flush=True)
    os.execvp(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.instant_html_renderer:app",
            "--host",
            host,
            "--port",
            port,
            "--proxy-headers",
            "--forwarded-allow-ips",
            "*",
        ],
    )


def _exec_worker() -> None:
    os.execvp(sys.executable, [sys.executable, "scripts/deck_processing_worker.py"])


def resolve_runtime_role(environ: dict[str, str] | None = None) -> str:
    source = os.environ if environ is None else environ
    configured_role = str(source.get("APP_ROLE") or "").strip().lower()
    service_name = str(source.get("RAILWAY_SERVICE_NAME") or "").strip().lower()
    service_kind = SERVICE_WORKER_KINDS.get(service_name)
    if service_kind:
        expected_role = f"worker-{service_kind.replace('_', '-')}"
        if not configured_role:
            source["APP_ROLE"] = "worker"
            return "worker"
        if normalize_name(configured_role) not in {"worker", normalize_name(expected_role)}:
            raise RuntimeError("Known Railway worker service has a conflicting APP_ROLE")
        return configured_role
    return configured_role or "api"


def main() -> None:
    revision_file = PROJECT_ROOT / "BUILD_REVISION"
    if revision_file.exists():
        print(f"deck_build_revision={revision_file.read_text().strip()}", flush=True)
    _prepare_runtime_defaults()
    app_role = resolve_runtime_role()

    if is_instant_html_renderer_role(app_role):
        # The API migration owner prepares the shared core schema. This service
        # has no auth/provider configuration and must never become a migration
        # or product-API process.
        _exec_instant_html_renderer()
        return

    if app_role == "worker" or app_role.startswith("worker-"):
        # Workers still need the runtime repair so they do not crash on stale production schemas.
        if _truthy(os.getenv("RUN_WORKER_MIGRATIONS_ON_STARTUP"), default=False):
            _run_migrations_if_enabled()
        else:
            migration_env = {**os.environ, "APP_ROLE": "migration"}
            try:
                _run_runtime_schema_bootstrap(migration_env)
            except subprocess.CalledProcessError as exc:
                if not _truthy(os.getenv("ALLOW_MIGRATION_FAILURE_ON_STARTUP"), default=_is_railway()):
                    raise
                print(
                    "WARNING: Worker runtime schema bootstrap failed during Railway startup. "
                    "Continuing so the worker can start and expose health diagnostics. "
                    f"Exit code: {exc.returncode}",
                    flush=True,
                )
        _exec_worker()
        return

    _run_migrations_if_enabled()
    _exec_api()


if __name__ == "__main__":
    main()
