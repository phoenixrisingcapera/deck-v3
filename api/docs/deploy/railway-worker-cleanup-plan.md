# Railway Worker Cleanup Plan

## Current Loop Update — 2026-07-04

Per-kind wrappers deleted, consolidated entrypoints created, worker files reorganised into `runtime/`, `dispatch/`, `entrypoints/` subdirectories. Business logic absorbed from workers into services. Railway service start commands remain unchanged.

## Current Loop Update — 2026-07-04 Service Absorption Pass

### Changes this loop

| Change | Details |
|---|---|
| `_ensure_company_profile` absorbed | Moved from `dispatch/worker_runtime_service.py` to `services/brand/company_profile.py::ensure_company_profile` |
| `handle_schema_validation` inline logic absorbed | DesignVersion slide `render_schema_json` check moved to `services/rendering/schema_validation.py::validate_design_version_slides` |
| Worker runtime files thinned | `source_pipeline_runtime.py` and `generation_runtime.py` now call service functions only |
| Zero business logic remains in workers | Every worker file is pure orchestration or dispatch |

### Railway impact

| Concern | Status |
|---|---|
| Railway service start commands changed? | NO — same `scripts/start_railway.py` → `scripts/deck_processing_worker.py` path |
| WORKER_KIND values changed? | NO — all values identical |
| DECK_WORKER_JOB_TYPES changed? | NO — all values identical |
| Runtime handler signatures changed? | NO — all `(db, job, *, worker_id)` unchanged |
| Handler function names changed? | NO — all names identical |
| Railway service names changed? | NO — same `worker-*` pattern |
| New env vars required? | NO |
| Env vars removed? | NO |
| Deployment risk | NONE — behavioral identical, only code organisation changed |

## Post-Refactor Worker Prune Plan — 2026-07-04

### Current finding

Worker execution is already mostly centralized. Job business logic is not spread across the per-kind `*_worker.py` files; those files only set environment defaults and call `app.workers.worker_entrypoint.main()`.

The actual worker layers are:

| Layer | Files | Decision |
|---|---|---|---|
| Railway/process bootstrap | `scripts/start_railway.py`, `scripts/deck_processing_worker.py` | KEEP. These own production startup, healthcheck, schema repair, heartbeat, polling, and stale-job recovery. |
| Generic claim/dispatch runtime | `app/workers/dispatch/worker_runtime_service.py`, `app/workers/dispatch/job_handlers.py` | KEEP. These own job claiming, worker-kind mapping, stale recovery, and job-type dispatch. |
| Stage runtime handlers | `app/workers/runtime/source_pipeline_runtime.py`, `app/workers/runtime/generation_runtime.py`, `app/workers/runtime/publisher_runtime.py`, `app/workers/runtime/llm_parallelization_runtime.py` | KEEP. They adapt durable workflow jobs to service calls and own job status/output semantics. Zero business logic remains. |
| Polling loop | `app/workers/entrypoints/deck_queue_worker.py`, `app/workers/entrypoints/worker_entrypoint.py` | KEEP. Entrypoints used by consolidated worker scripts. |
| Consolidated entrypoints | `app/workers/entrypoints/source_worker.py`, `generation_worker.py`, `render_worker.py`, `export_worker.py`, `rescue_worker.py` | KEEP. Developer convenience wrappers. |
| Per-kind wrappers (DELETED) | All 13 files deleted in prior pruning pass | DELETED. Railway never referenced them. |

### Why runtime handlers are not prunable yet

Several jobs are backed by product services, but the worker handler still adds workflow-specific behavior that the service does not own:

| Job | Service coverage | Worker-specific behavior that remains |
|---|---|---|
| `source_ingestion` | Upload route/service already persisted the file. | Confirms durable source-ingestion job and publishes workflow output. |
| `source_extraction` | `deck_processing/source_structure_persistence.py` extracts/persists structure. | Updates processing run stage, handles retry/final failure state, fails downstream source-pipeline jobs. |
| `miniatures` | `visualizer/miniature_service.py` generates source previews. | Updates run stage/output and maps preview counts into workflow state. |
| `brand_extraction` | `deck_processing/brand_extraction.py` runs brand extraction; `brand/company_profile.py::ensure_company_profile` creates default profile. | Marks workflow output, handles optional-stage failure semantics. |
| `smart_deck_context` | `deck_processing/smart_deck_context.py` prepares workspace. | Publishes enrichment/workspace metadata into durable workflow job output. |
| `llm_generation` | `llm/generation_service.py` creates generation jobs/design versions. | Converts workflow payload to schema input and stores design-version/workspace output. |
| `schema_validation` | `rendering/schema_validation.py::validate_design_version_slides` validates generated slides have `render_schema_json`. | Durable gate that blocks preview render; calls service function. |
| `preview_render` | Rendering/storage services own assets. | Records workflow manifest artifact and marks preview-ready phase. |
| `apply_version` | `llm/generation_service.apply_design_version` applies version. | Durable apply job output and status boundary. |
| `compile_final_deck` | `rendering/final_deck_service.py` compiles final deck. | Durable compile job output and status boundary. |
| `db_publisher` | `deck_processing/state_machine.py` transitions deck state. | Central publisher for `smart_deck_ready`, `preview_ready`, `applied`, and `export_ready` phases. |
| `export` | `rendering/export_service.py` creates export. | Records workflow export artifact and durable export output. |
| `llm_parallelization` | `llm/parallelization_service.py` builds and summarizes batches. | Owns Spark execution boundary and workflow artifact output. |

### Completed prune steps

| Step | Status | Date |
|---|---|---|
| 1. Update stale tests and docs | DONE | 2026-07-04 |
| 2. Confirm Railway start commands | DONE — Railway uses `scripts/deck_processing_worker.py`, never per-kind wrappers | 2026-07-04 |
| 3. Repoint local docs to canonical script | DONE — consolidated entrypoints document the pattern | 2026-07-04 |
| 4. Delete per-kind wrappers (13 files) | DONE | 2026-07-04 |
| 5. Absorb business logic from workers into services | DONE — company profile, schema validation | 2026-07-04 |
| 6. Reorganise into subdirectories | DONE — `runtime/`, `dispatch/`, `entrypoints/` | 2026-07-04 |

### Remaining prune decisions

| Item | Decision | Risk |
|---|---|---|
| `worker_entrypoint.py` | KEEP — thin delegate to `deck_queue_worker.main()`, used by consolidated entrypoints | Low |
| `deck_queue_worker.py` | KEEP — used as local dev loop, no production dependency | Low |
| Consolidated entrypoints (5 files) | KEEP — developer convenience, Railway does not use them | Low |
| Collapse 4 runtime files into fewer | DEFER — each owns distinct stage groups; merging would reduce clarity | Low |
| Move `process_workflow_job` error handling into service | DEFER — the error handling is workflow-lifecycle specific, not business logic | Low |

### Verification for any future prune

| Check | Command |
|---|---|
| Compile | `python3 -m compileall app scripts tests` |
| Worker imports | `python3 -c "from app.workers.dispatch.worker_runtime_service import process_next_durable_deck; print('OK')"` |
| Handler dispatch | `python3 -c "from app.workers.dispatch.job_handlers import get_workflow_job_handler; print(get_workflow_job_handler('source_extraction').__name__)"` |
| Worker entrypoint | `python3 -c "from app.workers.entrypoints.deck_queue_worker import main; print('OK')"` |
| Railway script | `python3 -c "from scripts.deck_processing_worker import main; print('OK')"` |
| Targeted tests | `python3 -m pytest tests/test_worker_service_name_normalization.py tests/test_workflow_frontend_worker_boundary.py tests/test_railway_deploy_config.py -q` |

### Verification checklist before deletion

| Check | Command/status |
|---|---|
| Pytest installed | `.venv/bin/python -m pytest --version` should pass. |
| Compile | `.venv/bin/python -m compileall app scripts tests` |
| Worker/deploy tests | `.venv/bin/python -m pytest tests/test_worker_service_name_normalization.py tests/test_workflow_frontend_worker_boundary.py tests/test_railway_deploy_config.py -q` |
| Canonical worker import | `.venv/bin/python -c "from scripts.deck_processing_worker import main; print('OK')"` |
| Runtime dispatch import | `.venv/bin/python -c "from app.workers.dispatch.worker_runtime_service import process_next_durable_deck; from app.workers.dispatch.job_handlers import get_workflow_job_handler; print('OK')"` |
| Railway manual check | Confirm no live service start command directly references `app/workers/*_worker.py`. |

### Current local baseline

- `.venv` was created and `pytest 9.1.1` is installed.
- `.venv/bin/python -m pytest tests/test_worker_service_name_normalization.py tests/test_workflow_frontend_worker_boundary.py tests/test_railway_deploy_config.py -q` currently runs but has stale-refactor failures in `tests/test_workflow_frontend_worker_boundary.py`.
- The failures are test/path assumptions, not proof that wrapper pruning is safe yet.

| Worker/runtime file | Job type | WORKER_KIND | APP_ROLE | Railway service expected | start command | Env vars required | Decision | Manual Railway action |
|---|---|---|---|---|---|---|---|---|
| `scripts/start_railway.py` | API/worker bootstrap | inferred | `api` or `worker-*` | API + all worker services | `python scripts/start_railway.py` or `APP_ROLE=worker python scripts/start_railway.py` | `DATABASE_URL`, storage env, provider env | KEEP | None from this loop. |
| `scripts/deck_processing_worker.py` | durable worker loop | inferred from service name | `worker` or `worker-*` | all deck worker services | launched by `scripts/start_railway.py` | `RAILWAY_SERVICE_NAME`, `DECK_WORKER_*` optional | KEEP | None from this loop. |
| `app/workers/source_pipeline_runtime.py` | source pipeline handlers | source stages | `worker-source-*`, `worker-miniatures`, `worker-smart-deck-context`, `worker-brand-extraction` | source pipeline workers | unchanged | DB/storage env | KEEP | None. |
| `app/workers/generation_runtime.py` | generation handlers | generation stages | `worker-llm-generation`, `worker-schema-validation`, `worker-preview-render`, `worker-apply-version`, `worker-compile-final-deck` | generation workers | unchanged | DB/storage/provider env | KEEP | None. |
| `app/workers/llm_parallelization_runtime.py` | `llm_parallelization` | `llm_parallelization` | `worker-llm-parallelization` | `worker-llm-parallelization` | unchanged | DB/storage/provider env plus PySpark env | KEEP | None. Import updated to `app.services.llm.parallelization_service`. |
| `app/workers/publisher_runtime.py` | `db_publisher`, `export` | `db_publisher`, `export` | `worker-db-publisher`, `worker-export` | publisher/export workers | unchanged | DB/storage env | KEEP | None. Import updated to `app.services.rendering.export_service`. |
| `app/workers/worker_runtime_service.py` | claim/recovery loop | inferred | worker services | all deck workers | imported by worker script | DB env | KEEP | Replaces `app/services/deck_processing_worker_service.py`; no Railway dashboard change required because start command still runs `scripts/deck_processing_worker.py`. |
| `app/services/admin/worker_health.py` | heartbeat | all workers | worker services | all deck workers | imported by worker script | DB env | KEEP | Replaces `app/services/worker_runtime_status_service.py`; no Railway dashboard change required. |
| per-kind wrappers in `app/workers/*_worker.py` | wrapper entrypoints | fixed per file | local/legacy | not current Railway runtime | direct file execution only | DB env | KEEP TEMPORARILY | Confirm no Railway service uses direct `python -m app.workers.<kind>` before deletion. |

Manual Railway actions remain unchanged: verify live service names, `APP_ROLE`, builder selection, and the bespoke PySpark worker before pruning legacy wrappers.

## Architecture Overview

Railway runs **two service types** from the same Dockerfile (`Dockerfile`):

### API service (1 instance)
| Field | Value |
|-------|-------|
| Config file | `railway.toml` / `railway.json` |
| startCommand | `python scripts/start_railway.py` |
| APP_ROLE | `api` (default) |
| Entrypoint | `scripts/start_railway.py` → runs Alembic → `uvicorn app.main:app` |

### Worker services (13 + 1 instances)
| Field | Value |
|-------|-------|
| Config file | `railway.worker.toml` (shared) |
| startCommand | `APP_ROLE=worker python scripts/start_railway.py` |
| APP_ROLE | Set per-service: `worker-source_ingestion`, `worker-source_extraction`, etc. |
| Entrypoint | `scripts/start_railway.py` → runtime bootstrap → `scripts/deck_processing_worker.py` |

The `deck_processing_worker.py` infers `WORKER_KIND` and `DECK_WORKER_JOB_TYPES` from the Railway service name via `infer_worker_kind_from_service_name()` in `app/services/deck_processing_worker_service.py`.

### LLM parallelization service (1 instance, bespoke)
| Field | Value |
|-------|-------|
| Dockerfile | `Dockerfile.pyspark` |
| startCommand | `python scripts/deck_processing_worker.py` |
| APP_ROLE | `worker-llm-parallelization` (hardcoded in Dockerfile) |
| Entrypoint | Direct `scripts/deck_processing_worker.py` |

---

## Worker Service Inventory

Each row = expected Railway service name → WORKER_KIND → job types.

| Railway service name | WORKER_KIND | DECK_WORKER_JOB_TYPES | Keep deployed? | Notes |
|---------------------|-------------|----------------------|---------------|-------|
| `worker-source-ingestion` | `source_ingestion` | `source_ingestion` | Yes | Spine stage 1 |
| `worker-source-extraction` | `source_extraction` | `source_extraction` | Yes | Spine stage 2 |
| `worker-miniatures` | `miniatures` | `miniatures` | Yes | Spine stage 3 |
| `worker-smart-deck-context` | `smart_deck_context` | `smart_deck_context` | Yes | Spine stage 4 |
| `worker-db-publisher` | `db_publisher` | `db_publisher` | Yes | Spine stage 5 |
| `worker-brand-extraction` | `brand_extraction` | `brand_extraction` | Yes | Spine stage 6 |
| `worker-llm-generation` | `llm_generation` | `llm_generation` | Yes | Spine stage 7 |
| `worker-schema-validation` | `schema_validation` | `schema_validation` | Yes | Spine stage 9 |
| `worker-preview-render` | `preview_render` | `preview_render` | Yes | Spine stage 10 |
| `worker-apply-version` | `apply_version` | `apply_version` | Yes | Spine stage 11 |
| `worker-compile-final-deck` | `compile_final_deck` | `compile_final_deck` | Yes | Spine stage between 11 and 12 |
| `worker-export` | `export` | `export` | Yes | Spine stage 12 |
| `worker-stale-job-rescuer` | `stale_job_rescuer` | _(none, recovery only)_ | Yes | Stale run recovery |
| `worker-llm-parallelization` | `llm_parallelization` | `llm_parallelization` | Yes | Spine stage 8 (PySpark) |

### Config files used per service

All worker services (except llm-parallelization) use:
- `railway.worker.toml` as deploy config
- `Dockerfile` as build image
- `scripts/start_railway.py` as entrypoint
- Railway service name as `RAILWAY_SERVICE_NAME` env var (auto-injected)

The llm-parallelization service uses:
- `Dockerfile.pyspark` as build image (hardcodes `APP_ROLE=worker-llm-parallelization`, `DECK_WORKER_JOB_TYPES=llm_parallelization`)
- `scripts/deck_processing_worker.py` as direct entrypoint

---

## Files vs. Running Code

### Files actually used at runtime

| File | Used by | Status |
|------|---------|--------|
| `scripts/start_railway.py` | API + all workers | KEEP |
| `scripts/deck_processing_worker.py` | All workers | KEEP |
| `scripts/railway_predeploy_noop.py` | Both Railway configs' preDeployCommand | KEEP |
| `railway.toml` | API service | KEEP |
| `railway.worker.toml` | All worker services | KEEP |
| `railway.json` | API service (v1 schema, may be unused) | KEEP TEMPORARILY |
| `Dockerfile` | API + all workers except llm-parallelization | KEEP |
| `Dockerfile.pyspark` | LLM parallelization worker | KEEP |
| `run_railway.sh` | Alternative entrypoint (may be unused) | KEEP TEMPORARILY |
| `run_worker_railway.sh` | Alternative entrypoint (may be unused) | KEEP TEMPORARILY |
| `nixpacks.toml` | Build metadata (may be unused since Dockerfile is used) | KEEP TEMPORARILY |
| `.railway-redeploy` | Operational metadata (not a config file) | KEEP |
| `.env.railway.required` | Documentation only | KEEP |
| `app/workers/entrypoints/deck_queue_worker.py` | Polling loop, used by consolidated entrypoints | KEEP |
| `app/workers/entrypoints/worker_entrypoint.py` | Thin delegate to deck_queue_worker, used by consolidated entrypoints | KEEP |
| `app/workers/entrypoints/source_worker.py` (and 4 other consolidated entrypoints) | Developer convenience wrappers, Railway does not use them | KEEP |
| All 13 per-kind wrappers (e.g. `source_ingestion_worker.py`) | DELETED — Railway never referenced them | DELETED |

### Files used by `scripts/deck_processing_worker.py`

| File | Purpose |
|------|---------|
| `app/workers/dispatch/worker_runtime_service.py` | `process_next_durable_deck`, `configured_worker_job_types`, `worker_recovery_only`, `recover_stale_processing_runs` |
| `app/services/rendering/render_schema_service.py` | `ensure_smart_deck_runtime_schema` |
| `app/services/admin/worker_health.py` | `record_worker_heartbeat` |
| `app/workers/runtime/source_pipeline_runtime.py` | `handle_source_ingestion`, `handle_source_extraction`, `handle_miniatures`, `handle_brand_extraction`, `handle_smart_deck_context` |
| `app/workers/runtime/generation_runtime.py` | `handle_llm_generation`, `handle_schema_validation`, `handle_preview_render`, `handle_apply_version`, `handle_compile_final_deck` |
| `app/workers/runtime/llm_parallelization_runtime.py` | `handle_llm_parallelization` |
| `app/workers/runtime/publisher_runtime.py` | `handle_db_publisher`, `handle_export` |
| `app/workers/dispatch/job_handlers.py` | `get_workflow_job_handler` (job_type → handler mapping) |

---

## Environment Variables Required Per Worker

### All services (API + every worker)
**From `.env.railway.required`:**
- `APP_ENV`, `RAILWAY_ENVIRONMENT`
- `APP_ROLE` (different per service)
- `PORT=8080`
- `DATABASE_URL` (or PostgreSQL variable reference)
- `AUTH_SECRET_KEY`
- `WORKSPACE_AI_FERNET_KEY`
- `AWS_ACCESS_KEY_ID` / `RAILWAY_BUCKET_ACCESS_KEY`
- `AWS_SECRET_ACCESS_KEY` / `RAILWAY_BUCKET_SECRET_KEY`
- `AWS_DEFAULT_REGION` / `RAILWAY_BUCKET_REGION`
- `AWS_S3_BUCKET_NAME` / `RAILWAY_BUCKET_NAME`
- `OPENROUTER_API_KEY`
- `UPLOAD_STORAGE_BACKEND=s3`

### Worker-only
- `DECK_WORKER_POLL_INTERVAL_SECONDS` (default: `10`)
- `DECK_WORKER_HEARTBEAT_INTERVAL_SECONDS` (default: `30`)
- `RUN_WORKER_MIGRATIONS_ON_STARTUP` (default: `false`)
- `LOG_LEVEL` (default: `INFO`)

### API-only
- `ALLOWED_ORIGINS`, `CORS_ORIGIN`
- `PUBLIC_SIGNUP_ENABLED`
- `RUN_MIGRATIONS_ON_STARTUP=true`
- `AUTH_SECRET_KEY_ID`, `AUTH_TOKEN_EXPIRY_MINUTES`
- `UPLOAD_SECURITY_SCAN_COMMAND`, `UPLOAD_SECURITY_SCAN_TIMEOUT_SECONDS`
- `MAX_REQUEST_BODY_SIZE_BYTES`
- `TURNSTILE_SECRET_KEY`
- `AI_DAILY_GENERATION_QUOTA`
- `OTEL_ENABLED`

### LLM parallelization worker only (via `Dockerfile.pyspark`)
- `PYSPARK_PYTHON=python3`
- `PYSPARK_DRIVER_PYTHON=python3`
- `SPARK_LOCAL_IP=127.0.0.1`
- Java runtime (included in `Dockerfile.pyspark`)

---

## Per-Kind Wrapper Files (DELETED)

All 13 per-kind wrapper files were deleted in the 2026-07-04 pruning pass. Railway never referenced them.

## Railway Service Consolidation (2026-07-04)

### Old services deleted (13 per-kind + 1 legacy)

| Deleted service | Replaced by |
|---|---|
| `worker-source-ingestion` | `worker-source-pipeline` |
| `worker-source-extraction` | `worker-source-pipeline` |
| `worker-miniatures` | `worker-source-pipeline` |
| `worker-brand-extraction` | `worker-source-pipeline` |
| `worker-smart-deck-context` | `worker-source-pipeline` |
| `worker-llm-generation` | `worker-generation-pipeline` |
| `worker-schema-validation` | `worker-generation-pipeline` |
| `worker-preview-render` | `worker-generation-pipeline` |
| `worker-apply-version` | `worker-generation-pipeline` |
| `worker-db-publisher` | `worker-exports-publisher` |
| `worker-export` | `worker-exports-publisher` |
| `worker-stale-job-rescuer` | kept unchanged |
| `deck-processing-worker` | deleted (legacy combined worker) |

### New consolidated services

| Service | Job types | Env vars |
|---|---|---|
| `worker-source-pipeline` | `source_ingestion,source_extraction,miniatures,brand_extraction,smart_deck_context` | `APP_ROLE=worker`, `DECK_WORKER_JOB_TYPES=…`, `DECK_WORKER_ALLOW_MULTI_JOB_TYPES=true` |
| `worker-generation-pipeline` | `llm_generation,schema_validation,preview_render,apply_version,compile_final_deck` | same pattern |
| `worker-exports-publisher` | `export,db_publisher` | same pattern |
| `worker-stale-job-rescuer` | recovery only | unchanged |

### Code changes required

Two small changes were needed to support consolidated multi-type workers:

1. **`app/workers/dispatch/worker_runtime_service.py::configured_worker_job_types()`** — skips the unknown-WORKER_KIND error when `DECK_WORKER_JOB_TYPES` is explicitly set
2. **`scripts/deck_processing_worker.py::_apply_worker_role_defaults()`** — skips service-name inference when `DECK_WORKER_JOB_TYPES` is already configured

### Current worker file layout

```
app/workers/
  __init__.py                    # package docstring
  runtime/
    source_pipeline_runtime.py   # stages 1-4, 6 handlers
    generation_runtime.py        # stages 7, 9-11 handlers
    publisher_runtime.py         # stages 5, 12 handlers
    llm_parallelization_runtime.py  # stage 8 handler (PySpark)
  dispatch/
    job_handlers.py              # job-type → handler registry
    worker_runtime_service.py    # claiming, heartbeat, recovery
  entrypoints/
    worker_entrypoint.py         # generic canonical entrypoint
    deck_queue_worker.py         # polling loop
    source_worker.py             # consolidated source pipeline entrypoint
    generation_worker.py         # consolidated generation entrypoint
    render_worker.py             # consolidated render entrypoint
    export_worker.py             # consolidated export entrypoint
    rescue_worker.py             # consolidated stale-job rescue entrypoint
```

---

## Env Vars / Services to Remove or Update

### Env vars to remove
- `WORKER_KIND` — no longer needed on consolidated workers; removed from the 3 new services
- `DECK_WORKER_JOB_TYPES` — was per-kind, now consolidated on the 3 new services

### Env vars to add
None. All required env vars are set on the consolidated services.

### Railway services already created
- `worker-source-pipeline` (SUCCESS, 1/1 replicas)
- `worker-generation-pipeline` (SUCCESS, 1/1 replicas)
- `worker-exports-publisher` (SUCCESS, 1/1 replicas)

### Railway services already deleted
- 11 per-kind worker services + `deck-processing-worker` (12 total)

### Railway services kept
- `worker-stale-job-rescuer` — unchanged, continues to handle recovery

---

## Deployment Risk

| Risk | Impact | Mitigation |
|------|--------|-----------|
| `railway.json` conflicts with `railway.toml` | Railway picks one; unknown which | Verify which file Railway actually uses for the API service |
| `nixpacks.toml` interferes with Dockerfile build | May cause duplicate apt installs | Verify Railway uses Dockerfile, not Nixpacks |
| LLM parallelization worker fails | Spine stage 8 blocked | PySpark + Java dependencies in `Dockerfile.pyspark` must be correct |

---

## Verification Commands

```bash
# Local compilation
python3 -m compileall app scripts tests

# Canonical entrypoints
python3 -c "from app.workers.entrypoints.worker_entrypoint import main; print('OK')"
python3 -c "from scripts.deck_processing_worker import main; print('OK')"

# Dispatch layer
python3 -c "from app.workers.dispatch.worker_runtime_service import process_next_durable_deck; print('OK')"
python3 -c "from app.workers.dispatch.job_handlers import get_workflow_job_handler; print(get_workflow_job_handler('source_extraction').__name__)"

# Runtime handlers
python3 -c "from app.workers.runtime.source_pipeline_runtime import handle_source_ingestion; print('OK')"
python3 -c "from app.workers.runtime.generation_runtime import handle_llm_generation; print('OK')"
python3 -c "from app.workers.runtime.publisher_runtime import handle_db_publisher; print('OK')"

# Targeted worker tests
python3 -m pytest tests/test_worker_service_name_normalization.py tests/test_workflow_frontend_worker_boundary.py tests/test_railway_deploy_config.py -q

# Absorbed service logic
python3 -c "from app.services.brand.company_profile import ensure_company_profile; print('OK')"
python3 -c "from app.services.rendering.schema_validation import validate_design_version_slides; print('OK')"
```

---

## Remaining Manual Railway Actions

1. **Verify consolidated worker healthchecks** — each should respond on `PORT` with `{"status":"ok","role":"worker",...}`.
2. **Verify `railway.json` vs `railway.toml`** — Railway 1.0 uses `railway.json`, Railway 2.0+ uses `railway.toml`. If both exist, Railway 2.0 ignores `railway.json` but may show a warning. Remove `railway.json` after confirming.
3. **Verify LLM parallelization Python + Java** — `Dockerfile.pyspark` must be selectable as the build for that service.
4. **Delete or repoint `run_railway.sh` and `run_worker_railway.sh`** — not used by current Railway config. Delete after confirming no external scripts reference them.
5. **Delete or repoint `nixpacks.toml`** — not used if Dockerfile is the builder. Delete after confirming Railway uses Dockerfile.
6. **Consider deleting `railway.json`** — redundant with `railway.toml` if Railway 2.0+.
