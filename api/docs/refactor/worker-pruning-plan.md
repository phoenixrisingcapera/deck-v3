# Worker Pruning Plan — Full Classification

## Classification Legend

| Label | Meaning |
|---|---|
| PACKAGE INIT | Empty or docstring-only `__init__.py` |
| ENTRYPOINT WRAPPER | Sets env vars, calls main(). Zero business logic. |
| DISPATCH | Registry / routing / claiming — minimal orchestration. |
| RUNTIME ORCHESTRATOR | Job lifecycle: claim → call service → set status → handle errors. |
| INFRASTRUCTURE | Environment setup (Spark, DB connections) that must live in worker process. |

## File-by-File Classification

### `app/workers/__init__.py`

| Field | Value |
|---|---|
| Classification | PACKAGE INIT |
| Job types handled | — |
| WORKER_KIND | — |
| DECK_WORKER_JOB_TYPES | — |
| Business logic present | no |
| Target service owner | — |
| Railway dependency | none |
| Can move now | no (package init) |
| Can delete now | no (package init) |
| Risk level | none |
| Verify | `python -c "import app.workers; print('OK')"` |

### `app/workers/entrypoints/worker_entrypoint.py`

| Field | Value |
|---|---|
| Classification | ENTRYPOINT WRAPPER |
| Job types handled | all (delegates to deck_queue_worker.main()) |
| WORKER_KIND | inferred from env at runtime |
| DECK_WORKER_JOB_TYPES | inferred from env at runtime |
| Business logic present | no |
| Target service owner | — |
| Railway dependency | none — Railway uses `scripts/deck_processing_worker.py` directly |
| Can move now | yes |
| Can delete now | no — needed by consolidated entrypoints |
| Risk level | low |
| Verify | `.venv/bin/python -c "from app.workers.entrypoints.worker_entrypoint import main; print('OK')"` |

### `app/workers/entrypoints/deck_queue_worker.py`

| Field | Value |
|---|---|
| Classification | DISPATCH + ORCHESTRATION |
| Job types handled | all (polling loop) |
| WORKER_KIND | inferred from env |
| DECK_WORKER_JOB_TYPES | inferred from env |
| Business logic present | no — pure polling loop with heartbeat and schema repair |
| Target service owner | — |
| Railway dependency | none — Railway uses `scripts/deck_processing_worker.py` (parallel implementation) |
| Can move now | yes |
| Can delete now | no — alternative local dev loop; used by consolidated entrypoints |
| Risk level | low |
| Verify | `.venv/bin/python -c "from app.workers.entrypoints.deck_queue_worker import main; print('OK')"` |

### `app/workers/entrypoints/source_worker.py`

| Field | Value |
|---|---|
| Classification | ENTRYPOINT WRAPPER |
| Job types handled | source pipeline (source_ingestion, source_extraction, miniatures, smart_deck_context, brand_extraction) |
| WORKER_KIND | `source_ingestion` (default, overridable) |
| DECK_WORKER_JOB_TYPES | `source_ingestion` (default, overridable) |
| Business logic present | no |
| Target service owner | — |
| Railway dependency | none — Railway uses `scripts/deck_processing_worker.py` + env vars |
| Can move now | yes |
| Can delete now | no — developer convenience entrypoint |
| Risk level | low |
| Verify | `.venv/bin/python -c "from app.workers.entrypoints.source_worker import main; print('OK')"` |

### `app/workers/entrypoints/generation_worker.py`

| Field | Value |
|---|---|
| Classification | ENTRYPOINT WRAPPER |
| Job types handled | llm_generation, schema_validation, preview_render, apply_version, compile_final_deck |
| WORKER_KIND | `llm_generation` (default, overridable) |
| DECK_WORKER_JOB_TYPES | `llm_generation` (default, overridable) |
| Business logic present | no |
| Target service owner | — |
| Railway dependency | none |
| Can move now | yes |
| Can delete now | no — developer convenience entrypoint |
| Risk level | low |
| Verify | `.venv/bin/python -c "from app.workers.entrypoints.generation_worker import main; print('OK')"` |

### `app/workers/entrypoints/render_worker.py`

| Field | Value |
|---|---|
| Classification | ENTRYPOINT WRAPPER |
| Job types handled | preview_render |
| WORKER_KIND | `preview_render` (default, overridable) |
| DECK_WORKER_JOB_TYPES | `preview_render` (default, overridable) |
| Business logic present | no |
| Target service owner | — |
| Railway dependency | none |
| Can move now | yes |
| Can delete now | no — developer convenience entrypoint |
| Risk level | low |
| Verify | `.venv/bin/python -c "from app.workers.entrypoints.render_worker import main; print('OK')"` |

### `app/workers/entrypoints/export_worker.py`

| Field | Value |
|---|---|
| Classification | ENTRYPOINT WRAPPER |
| Job types handled | export, db_publisher |
| WORKER_KIND | `export` (default, overridable) |
| DECK_WORKER_JOB_TYPES | `export` (default, overridable) |
| Business logic present | no |
| Target service owner | — |
| Railway dependency | none |
| Can move now | yes |
| Can delete now | no — developer convenience entrypoint |
| Risk level | low |
| Verify | `.venv/bin/python -c "from app.workers.entrypoints.export_worker import main; print('OK')"` |

### `app/workers/entrypoints/rescue_worker.py`

| Field | Value |
|---|---|
| Classification | ENTRYPOINT WRAPPER |
| Job types handled | all (recovery only) |
| WORKER_KIND | `stale_job_rescuer` |
| DECK_WORKER_JOB_TYPES | — (sets `DECK_WORKER_RECOVERY_ONLY=true`) |
| Business logic present | no |
| Target service owner | — |
| Railway dependency | none |
| Can move now | yes |
| Can delete now | no — developer convenience entrypoint |
| Risk level | low |
| Verify | `.venv/bin/python -c "from app.workers.entrypoints.rescue_worker import main; print('OK')"` |

### `app/workers/dispatch/job_handlers.py`

| Field | Value |
|---|---|
| Classification | DISPATCH |
| Job types handled | all — routing table only |
| WORKER_KIND | — |
| DECK_WORKER_JOB_TYPES | — |
| Business logic present | no |
| Target service owner | — |
| Railway dependency | imported by `worker_runtime_service.py` at runtime |
| Can move now | no — deeply wired into dispatch |
| Can delete now | no — active dispatch seam |
| Risk level | none |
| Verify | `.venv/bin/python -c "from app.workers.dispatch.job_handlers import get_workflow_job_handler; handler = get_workflow_job_handler('source_ingestion'); print(handler.__name__)"` |

### `app/workers/dispatch/worker_runtime_service.py`

| Field | Value |
|---|---|
| Classification | DISPATCH + ORCHESTRATION |
| Job types handled | all — claiming, heartbeat, recovery, processing |
| WORKER_KIND | all — kind inference, mapping, validation |
| DECK_WORKER_JOB_TYPES | all — configured job type resolution |
| Business logic present | no (after absorption: `_ensure_company_profile` moved to `app/services/brand/company_profile.py`) |
| Target service owner | — |
| Railway dependency | imported by `scripts/deck_processing_worker.py` at runtime |
| Can move now | no — core dispatch engine |
| Can delete now | no — active dispatch |
| Risk level | none |
| Verify | `.venv/bin/python -c "from app.workers.dispatch.worker_runtime_service import process_next_durable_deck; print('OK')"` |

### `app/workers/runtime/source_pipeline_runtime.py`

| Field | Value |
|---|---|
| Classification | RUNTIME ORCHESTRATOR |
| Job types handled | source_ingestion, source_extraction, miniatures, brand_extraction, smart_deck_context |
| WORKER_KIND | source pipeline kinds |
| DECK_WORKER_JOB_TYPES | source pipeline job types |
| Business logic present | no — all calls delegated to service functions |
| Target service owner | — |
| Railway dependency | imported at runtime via job_handlers dispatch |
| Can move now | no — active runtime |
| Can delete now | no — active runtime |
| Risk level | none |
| Verify | `.venv/bin/python -c "from app.workers.runtime.source_pipeline_runtime import handle_source_extraction; print('OK')"` |

### `app/workers/runtime/generation_runtime.py`

| Field | Value |
|---|---|
| Classification | RUNTIME ORCHESTRATOR |
| Job types handled | llm_generation, schema_validation, preview_render, apply_version, compile_final_deck |
| WORKER_KIND | generation pipeline kinds |
| DECK_WORKER_JOB_TYPES | generation job types |
| Business logic present | no (after absorption: `DesignVersion` slide validation moved to `app/services/rendering/schema_validation.py`) |
| Target service owner | — |
| Railway dependency | imported at runtime via job_handlers dispatch |
| Can move now | no — active runtime |
| Can delete now | no — active runtime |
| Risk level | none |
| Verify | `.venv/bin/python -c "from app.workers.runtime.generation_runtime import handle_llm_generation; print('OK')"` |

### `app/workers/runtime/publisher_runtime.py`

| Field | Value |
|---|---|
| Classification | RUNTIME ORCHESTRATOR |
| Job types handled | db_publisher, export |
| WORKER_KIND | publisher/export |
| DECK_WORKER_JOB_TYPES | db_publisher, export |
| Business logic present | no — calls `transition_deck_state`, `create_export` from services |
| Target service owner | — |
| Railway dependency | imported at runtime via job_handlers dispatch |
| Can move now | no — active runtime |
| Can delete now | no — active runtime |
| Risk level | none |
| Verify | `.venv/bin/python -c "from app.workers.runtime.publisher_runtime import handle_db_publisher; print('OK')"` |

### `app/workers/runtime/llm_parallelization_runtime.py`

| Field | Value |
|---|---|
| Classification | RUNTIME ORCHESTRATOR + INFRASTRUCTURE |
| Job types handled | llm_parallelization |
| WORKER_KIND | llm_parallelization |
| DECK_WORKER_JOB_TYPES | llm_parallelization |
| Business logic present | no — batch building/result summarizing delegated to `app/services/llm/parallelization_service.py` |
| Target service owner | — |
| Railway dependency | `Dockerfile.pyspark` image only |
| Can move now | no — Spark session management is worker-process specific |
| Can delete now | no — only handler for this job type |
| Risk level | medium — PySpark dependency |
| Verify | `Dockerfile.pyspark` image only (requires `pyspark`) |

### `app/workers/legacy/__init__.py` — **DELETED 2026-07-04**

Empty package init. No imports, no references, no Railway dependency. Safely deleted.

## Summary

| Category | Count | Files |
|---|---|---|
| PACKAGE INIT | 1 | `__init__.py` |
| ENTRYPOINT WRAPPER | 7 | `entrypoints/worker_entrypoint.py`, `entrypoints/source_worker.py`, `entrypoints/generation_worker.py`, `entrypoints/render_worker.py`, `entrypoints/export_worker.py`, `entrypoints/rescue_worker.py`, `entrypoints/deck_queue_worker.py` |
| DISPATCH | 1 | `dispatch/job_handlers.py` |
| DISPATCH + ORCHESTRATION | 1 | `dispatch/worker_runtime_service.py` |
| RUNTIME ORCHESTRATOR | 3 | `runtime/source_pipeline_runtime.py`, `runtime/generation_runtime.py`, `runtime/publisher_runtime.py` |
| RUNTIME ORCHESTRATOR + INFRASTRUCTURE | 1 | `runtime/llm_parallelization_runtime.py` |
| **Total** | **14** | |

## Business Logic Absorbed

| Logic | Previous location | New location |
|---|---|---|
| Default CompanyProfile creation | `worker_runtime_service.py::_ensure_company_profile` | `company_profile.py::ensure_company_profile` |
| DesignVersion slide render_schema_json validation | `generation_runtime.py::handle_schema_validation` (inline) | `schema_validation.py::validate_design_version_slides` |

After absorption: zero business logic remains in worker files. Every worker file is pure orchestration or dispatch.
