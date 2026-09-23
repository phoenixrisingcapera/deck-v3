# Worker Debugging Map

Maps each product-spine stage to the worker kind, job type, runtime handler, logs, and verify command.

## Source Ingestion (Stage 1)

| Field | Value |
|---|---|
| Worker kind | `source_ingestion` |
| Job type | `source_ingestion` |
| Runtime handler | `source_pipeline_runtime.py::handle_source_ingestion` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | `railway logs --service worker-source-ingestion` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.source_pipeline_runtime import handle_source_ingestion; import inspect; print(inspect.getfile(handle_source_ingestion))"` |

## Source Extraction (Stage 2)

| Field | Value |
|---|---|
| Worker kind | `source_extraction` |
| Job type | `source_extraction` |
| Runtime handler | `source_pipeline_runtime.py::handle_source_extraction` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | `railway logs --service worker-source-extraction` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.source_pipeline_runtime import handle_source_extraction; import inspect; print(inspect.getfile(handle_source_extraction))"` |

## Miniatures (Stage 3)

| Field | Value |
|---|---|
| Worker kind | `miniatures` |
| Job type | `miniatures` |
| Runtime handler | `source_pipeline_runtime.py::handle_miniatures` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | `railway logs --service worker-miniatures` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.source_pipeline_runtime import handle_miniatures; import inspect; print(inspect.getfile(handle_miniatures))"` |

## Smart Deck Context (Stage 4)

| Field | Value |
|---|---|
| Worker kind | `smart_deck_context` |
| Job type | `smart_deck_context` |
| Runtime handler | `source_pipeline_runtime.py::handle_smart_deck_context` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | `railway logs --service worker-smart-deck-context` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.source_pipeline_runtime import handle_smart_deck_context; import inspect; print(inspect.getfile(handle_smart_deck_context))"` |

## DB Publisher (Stage 5)

| Field | Value |
|---|---|
| Worker kind | `db_publisher` |
| Job type | `db_publisher` |
| Runtime handler | `publisher_runtime.py::handle_db_publisher` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | `railway logs --service worker-db-publisher` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.publisher_runtime import handle_db_publisher; import inspect; print(inspect.getfile(handle_db_publisher))"` |

## Brand Extraction (Stage 6)

| Field | Value |
|---|---|
| Worker kind | `brand_extraction` |
| Job type | `brand_extraction` |
| Runtime handler | `source_pipeline_runtime.py::handle_brand_extraction` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | `railway logs --service worker-brand-extraction` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.source_pipeline_runtime import handle_brand_extraction; import inspect; print(inspect.getfile(handle_brand_extraction))"` |

## LLM Generation (Stage 7)

| Field | Value |
|---|---|
| Worker kind | `llm_generation` |
| Job type | `llm_generation` |
| Runtime handler | `generation_runtime.py::handle_llm_generation` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | `railway logs --service worker-llm-generation` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.generation_runtime import handle_llm_generation; import inspect; print(inspect.getfile(handle_llm_generation))"` |

## LLM Parallelization (Stage 8)

| Field | Value |
|---|---|
| Worker kind | `llm_parallelization` |
| Job type | `llm_parallelization` |
| Runtime handler | `llm_parallelization_runtime.py::handle_llm_parallelization` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | `railway logs --service worker-llm-parallelization` |
| Verify | `Dockerfile.pyspark` image only; requires `pyspark` |

## Schema Validation (Stage 9, merged into generation_runtime)

| Field | Value |
|---|---|
| Worker kind | `llm_generation` |
| Job type | `schema_validation` |
| Runtime handler | `generation_runtime.py::handle_schema_validation` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | Backend logs for `validate_generated_deck` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.generation_runtime import handle_schema_validation; import inspect; print(inspect.getfile(handle_schema_validation))"` |

## Preview Render (Stage 10, merged into generation_runtime)

| Field | Value |
|---|---|
| Worker kind | `llm_generation` |
| Job type | `preview_render` |
| Runtime handler | `generation_runtime.py::handle_preview_render` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | Backend logs for `preview_render` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.generation_runtime import handle_preview_render; import inspect; print(inspect.getfile(handle_preview_render))"` |

## Apply Version (Stage 11, merged into generation_runtime)

| Field | Value |
|---|---|
| Worker kind | `llm_generation` |
| Job type | `apply_version` |
| Runtime handler | `generation_runtime.py::handle_apply_version` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | Backend logs for `apply_design_version` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.generation_runtime import handle_apply_version; import inspect; print(inspect.getfile(handle_apply_version))"` |

## Export (Stage 12)

| Field | Value |
|---|---|
| Worker kind | `export` |
| Job type | `export` |
| Runtime handler | `publisher_runtime.py::handle_export` |
| Dispatch entry | `dispatch/worker_runtime_service.py::process_next_durable_deck` |
| Logs | Backend logs for `create_export` |
| Verify | `.venv/bin/python -c "from app.workers.runtime.publisher_runtime import handle_export; import inspect; print(inspect.getfile(handle_export))"` |

## Stale Job Rescue (cross-cutting)

| Field | Value |
|---|---|
| Worker kind | `stale_job_rescuer` |
| Job type | all (recovery) |
| Runtime handler | `dispatch/worker_runtime_service.py::recover_stale_workflow_jobs` |
| Dispatch entry | `entrypoints/rescue_worker.py` (sets `DECK_WORKER_RECOVERY_ONLY`) |
| Logs | `railway logs --service worker-stale-job-rescuer` |
| Verify | `.venv/bin/python -c "from app.workers.dispatch.worker_runtime_service import recover_stale_workflow_jobs; import inspect; print(inspect.getfile(recover_stale_workflow_jobs))"` |

## Consolidated Entrypoints Quick Reference

| File | Default `WORKER_KIND` | Job types handled |
|---|---|---|
| `entrypoints/source_worker.py` | `source_ingestion` | `source_ingestion`, `source_extraction`, `miniatures`, `smart_deck_context`, `brand_extraction` |
| `entrypoints/generation_worker.py` | `llm_generation` | `llm_generation`, `schema_validation`, `preview_render`, `apply_version`, `compile_final_deck` |
| `entrypoints/render_worker.py` | `preview_render` | `preview_render` (standalone) |
| `entrypoints/export_worker.py` | `export` | `export`, `db_publisher` |
| `entrypoints/rescue_worker.py` | `stale_job_rescuer` | all (recovery only) |

## File Layout

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
    deck_queue_worker.py         # legacy polling loop
    source_worker.py             # consolidated source pipeline entrypoint
    generation_worker.py         # consolidated generation entrypoint
    render_worker.py             # consolidated render entrypoint
    export_worker.py             # consolidated export entrypoint
    rescue_worker.py             # consolidated stale-job rescue entrypoint
  legacy/                        # empty; Railway compatibility shims if needed
```
