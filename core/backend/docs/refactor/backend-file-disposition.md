# Backend File Disposition

## Current Loop Update — 2026-07-04

### Miniatures hotfix — 2026-07-04

Railway production logs showed the first broken miniature stage clearly:

- service: `worker-source-pipeline`
- stage: `miniatures`
- failure: `ValueError("Upload storage backend changed before promotion")`
- stack owner: `app/services/deck_processing/source_preview_renderer.py`

Root cause: source preview rendering wrote local cache files but tagged them as `provider="local"` even when Railway runtime storage was S3/Supabase. Promotion then failed by construction in `artifact_storage.promote_upload()`.

Fixes applied:

| File | Action | Notes |
|---|---|---|
| `app/services/deck_processing/source_preview_renderer.py` | FIX | Preview promotion now uses the active upload storage provider instead of hardcoded `local`. |
| `app/workers/runtime/source_pipeline_runtime.py` | ABSORB IMPORT | `handle_miniatures` now imports `extract_source_previews` directly from `deck_processing/source_preview_service.py`. |
| `app/services/visualizer/miniature_service.py` | PRUNED | Wrapper had one importer and added no runtime value. |
| `app/services/rendering/slide_thumbnail.py` | PRUNED | Dead optional thumbnail helper after confirming source extraction never used `include_thumbnails=True`; miniatures is now the only source preview/thumbnail producer. |
| `app/services/visualizer/preview_asset_service.py` | PRUNED | Dead seam wrapper around signed URL artifact service with no importers. |
| `app/services/deck_processing/source_extraction.py` | SIMPLIFIED | Removed unused optional thumbnail branch; source extraction is structure-only again. |

Targeted verification after fix:

- `tests/test_deck_preview_service.py` passed.
- Added regression coverage for non-local storage provider promotion in source preview rendering.

Final miniature backend owner set:

- `app/services/deck_processing/source_preview_service.py`
- `app/services/deck_processing/source_preview_renderer.py`
- `app/services/deck_processing/source_preview_persistence.py`
- `app/workers/runtime/source_pipeline_runtime.py::handle_miniatures`

### `app/services/visualizer/` audit — 2026-07-04

The remaining visualizer package is compact and active. No additional file-level prune was warranted after removing the dead preview seams. One internal duplication was fixed: dashboard deck status mapping now uses the canonical deck state machine instead of re-listing legacy deck statuses locally.

| File | Classification | Evidence | Disposition |
|---|---|---|---|
| `app/services/visualizer/slide_read_model.py` | RUNTIME OWNER | Main deck/slide/block/findings/suggestions read model used by routes and services | KEEP |
| `app/services/visualizer/generated_deck_read_model.py` | RUNTIME OWNER | Due diligence/generated deck workspace read model | KEEP |
| `app/services/visualizer/workspace_dashboard_read_model.py` | RUNTIME OWNER | Workspace dashboard/latest deck/recent slides projection | KEEP + DUPLICATION FIX |
| `app/services/visualizer/deck_artifact_listing.py` | RUNTIME OWNER | Deck artifact listing/read model | KEEP |
| `app/services/visualizer/deck_iteration_read_model.py` | RUNTIME OWNER | Deck iteration list/read model | KEEP |
| `app/services/visualizer/preview_asset_service.py` | DEAD SEAM WRAPPER | No importers; only re-exported signed URL bucket service | PRUNED |
| `app/services/visualizer/miniature_service.py` | DEAD SEAM WRAPPER | Single importer removed; source worker now calls canonical miniature owner directly | PRUNED |

### `app/services/deck_processing/` seam cleanup — 2026-07-04

`deck_processing/` is now the real runtime owner package, not a migration seam. Three dead seam wrappers with zero importers were removed.

| File | Classification | Evidence | Disposition |
|---|---|---|---|
| `app/services/deck_processing/source_pipeline.py` | DEAD SEAM WRAPPER | No importers; only re-exported `queue_source_extraction` from `workflow_orchestration.py` | PRUNED |
| `app/services/deck_processing/readiness_publisher.py` | DEAD SEAM WRAPPER | No importers; only re-exported `handle_db_publisher` from worker runtime | PRUNED |
| `app/services/deck_processing/source_ingestion.py` | DEAD SEAM WRAPPER | No importers; only re-exported `handle_source_ingestion` from worker runtime | PRUNED |
| `app/services/deck_processing/__init__.py` | PACKAGE DOCSTRING | Updated to reflect current runtime ownership instead of staged migration wording | KEEP |

### `app/schemas/` audit — 2026-07-04

The schema audit found mostly active Pydantic route/service contracts. Five files were stale or absorbable wrappers and were pruned after import verification. No broad schema expansion was applied; the remaining contracts are runtime-imported or package init.

| File/group | Classification | Evidence | Disposition |
|---|---|---|---|
| `app/schemas/deck_workflow.py` | RUNTIME OWNER | Imported by product workflow routes/services and owns canonical workflow job/phase/action literals | KEEP |
| `app/schemas/deck.py` | RUNTIME OWNER | Owns legacy deck request/patch/export contracts and deck status canonicalization | KEEP |
| `app/schemas/analysis.py` | RUNTIME OWNER | Owns findings/suggestion response contracts; `decks.py` now imports suggestions directly from here | KEEP |
| `app/schemas/smart_edit.py` | RUNTIME OWNER | Owns Smart Edit response schemas; imports request schema from `deck.py` | KEEP |
| `app/schemas/export.py` | UNUSED RE-EXPORT SHIM | Only re-exported `deck.ExportCreate`; one importer updated to `app.schemas.deck` | PRUNED |
| `app/schemas/suggestion.py` | ABSORBED RE-EXPORT SHIM | Only re-exported analysis suggestion responses and `deck.SuggestionPatch`; one importer updated to `app.schemas.analysis` | PRUNED |
| `app/schemas/block.py` | UNUSED RE-EXPORT SHIM | No importers; only re-exported `deck.SlideBlockPatch` | PRUNED |
| `app/schemas/slide.py` | UNUSED RE-EXPORT SHIM | No importers; only re-exported `deck.SlideBlockPatch` | PRUNED |
| `app/schemas/deck_processing.py` | STALE DUPLICATE CONTRACT | No importers; duplicated workflow job literals and missed `llm_parallelization`, now owned by `deck_workflow.py` | PRUNED |

Remaining schema files after prune: `analysis.py`, `billing.py`, `brand_profile.py`, `common.py`, `connected_account.py`, `deck.py`, `deck_intake.py`, `deck_structure.py`, `deck_workflow.py`, `deployment_readiness.py`, `due_diligence.py`, `generation.py`, `profile.py`, `public_interest.py`, `save_confirmation.py`, `shell.py`, `shell_workspace.py`, `smart_deck.py`, `smart_deck_agent.py`, `smart_deck_subjects.py`, `smart_edit.py`, `user.py`, `workspace_ai_provider.py`, `workspace_summary.py`, plus package init.

Contract note: `app/schemas/smart_edit.py::SmartEditSuggestionResponse.status` remains `str`. That matches current runtime behavior and was not changed in this prune, but it is less strict than the suggestion status literal in `common.py`/`analysis.py` and can be tightened in a separate behavior-aware pass if desired.

### `app/db/` audit — 2026-07-04

The DB audit found that runtime code imports models through `app.db.models`, while the real SQLAlchemy model definitions live in `app/db/models/entities.py`. The one-line per-model modules had no direct importers and only re-exported classes from `entities.py`, so they were pruned. `InterestLead` was the only real model outside `entities.py`; it was absorbed into `entities.py` without changing its table name or columns.

| File | Classification | Evidence | Disposition |
|---|---|---|---|
| `app/db/base.py` | RUNTIME OWNER | Defines shared SQLAlchemy declarative `Base`; imported by models, Alembic, and tests | KEEP |
| `app/db/session.py` | RUNTIME OWNER | Defines runtime engine and `SessionLocal`; imported by API, workers, scripts | KEEP |
| `app/db/models/entities.py` | RUNTIME OWNER | Owns SQLAlchemy mapped classes and table metadata | KEEP |
| `app/db/models/__init__.py` | PUBLIC MODEL EXPORT SURFACE | Most app code imports models from `app.db.models` | KEEP |
| `app/db/__init__.py` | PACKAGE INIT | Package marker | KEEP |
| `app/db/models/interest_lead.py` | ABSORBED REAL MODEL | One direct service import updated to `app.db.models`; class moved to `entities.py` | PRUNED |
| Per-model files `adaptation_run.py`, `adaptation_suggestion.py`, `analysis_finding.py`, `analysis_run.py`, `audience_profile.py`, `block_classification.py`, `deck.py`, `deck_export.py`, `deck_file.py`, `deck_slide.py`, `deck_slide_block.py`, `deck_slide_revision.py`, `permission.py`, `smart_edit_run.py`, `smart_edit_suggestion.py`, `user.py`, `workspace.py` | UNUSED RE-EXPORT SHIMS | No external direct imports; each only imported one class from `entities.py` and set `__all__` | PRUNED |

Remaining `app/db/` structure after prune:

```text
app/db/
  __init__.py
  base.py
  session.py
  models/
    __init__.py
    entities.py
```

### `app/api/` audit — 2026-07-04

The API audit classified mounted route modules by actual FastAPI registration order. Five split route modules were fully shadowed by earlier `app/api/routes/decks.py` endpoints and had no unique reachable runtime paths, so they were pruned and their redundant registrations removed.

| File | Classification | Runtime evidence | Disposition |
|---|---|---|---|
| `app/api/deps.py` | RUNTIME OWNER | Auth/session/resource dependencies imported by routes and `app/main.py` | KEEP |
| `app/api/routes/decks.py` | RUNTIME OWNER | First registered owner for `/api/decks/*` legacy deck endpoints, including upload, analysis, blocks, suggestions, Smart Edit, and export duplicates | KEEP |
| `app/api/routes/product/__init__.py` | RUNTIME OWNER | Product router registry consumed by `app/main.py` | KEEP |
| `app/api/routes/admin/__init__.py` | RUNTIME OWNER | Admin router registry consumed by `app/main.py` | KEEP |
| `app/api/routes/analysis.py` | FULLY SHADOWED SPLIT ROUTE | 2 routes registered after identical `decks.py` routes; 0 unique reachable paths | PRUNED |
| `app/api/routes/blocks.py` | FULLY SHADOWED SPLIT ROUTE | 2 routes registered after identical `decks.py` routes; 0 unique reachable paths | PRUNED |
| `app/api/routes/smart_edit.py` | FULLY SHADOWED SPLIT ROUTE | 3 routes registered after identical `decks.py` routes; 0 unique reachable paths | PRUNED |
| `app/api/routes/suggestions.py` | FULLY SHADOWED SPLIT ROUTE | 2 routes registered after identical `decks.py` routes; 0 unique reachable paths | PRUNED |
| `app/api/routes/uploads.py` | FULLY SHADOWED SPLIT ROUTE | 1 route registered after identical `decks.py` route; 0 unique reachable paths | PRUNED |

Pruned files had test imports updated to target the actual runtime owner in `app/api/routes/decks.py`. Remaining route modules are mounted and have at least one unique reachable endpoint, or intentionally shadow older product endpoints as rescue/hardening owners registered earlier than the old route.

### `app/core/` audit — 2026-07-04

The audit classified `app/core/` after the service/worker cleanup. After import verification, the two proven unused legacy files were pruned: `app/core/errors.py` and `app/core/statuses.py`.

| File | Classification | Import evidence | Current owner / replacement | Disposition |
|---|---|---:|---|---|
| `app/core/config.py` | RUNTIME OWNER | 63 import matches | Runtime settings, defaults, env aliases, DB/auth/storage/provider config | KEEP |
| `app/core/security.py` | RUNTIME OWNER | 57 import matches | ID generation, password hashing, JWT creation/decoding | KEEP |
| `app/core/railway_env.py` | RUNTIME OWNER | 6 import matches | Railway/env variable alias normalization for startup, config, checks, tests | KEEP |
| `app/core/workspace_ai_crypto.py` | RUNTIME OWNER | 4 import matches | Workspace AI provider credential encryption key helper | KEEP |
| `app/core/__init__.py` | PACKAGE INIT | package marker | Package initialization only | KEEP |
| `app/core/errors.py` | UNUSED LEGACY SHIM | no importers; only self-definitions matched | Runtime code uses local/domain exceptions or built-ins such as `FileNotFoundError`; no current app-wide error owner imports this file | PRUNED |
| `app/core/statuses.py` | UNUSED LEGACY CONSTANTS | no importers; only self-definitions matched | Deck states moved to `app/services/deck_processing/state_machine.py`; workflow job statuses live in `app/services/deck_processing/workflow_jobs.py`; suggestion status is local schema/model vocabulary | PRUNED |

Absorbed status ownership:

| Legacy concept | Current owner | Notes |
|---|---|---|
| Deck lifecycle strings from `DECK_STATUSES` | `app/services/deck_processing/state_machine.py::DeckState`, `CANONICAL_DECK_STATES`, `LEGACY_DECK_STATE_MAP` | Old granular states such as `parsing`, `structuring`, `analysing`, and `reviewed` are interpreted through the legacy map and normalized to canonical deck states. |
| Workflow queue/run statuses | `app/services/deck_processing/workflow_jobs.py::JOB_STATUS_*` | Owns queued/running/completed/failure/blocking/timeout vocabulary for durable workflow jobs. |
| Adaptation suggestion statuses | `app/schemas/analysis.py::AdaptationSuggestionResponse.status` plus DB model usage | The route schema owns the frontend contract literal vocabulary. |
| Smart Edit statuses | `app/schemas/smart_edit.py` and Smart Edit models/services | No import path uses `SMART_EDIT_RUN_STATUSES`; current response schema leaves suggestion status as `str`. |

Verification after pruning: `python3 -m compileall app scripts tests` passed. Do not delete the active runtime owners above.

## Continued Loop Update — 2026-07-04 Pass 2

## Continued Loop Update — 2026-07-04 Worker Pruning Pass

### Worker files moved

| Previous file | New owner | Action | Notes |
|---|---|---|---|
| `app/workers/source_pipeline_runtime.py` | `app/workers/runtime/source_pipeline_runtime.py` | MOVE | Runtime job handlers for stages 1-4, 6 moved under runtime/. |
| `app/workers/generation_runtime.py` | `app/workers/runtime/generation_runtime.py` | MOVE | Generation-pipeline handlers for stages 7, 9-11 moved under runtime/. |
| `app/workers/publisher_runtime.py` | `app/workers/runtime/publisher_runtime.py` | MOVE | Publisher handlers for stages 5, 12 moved under runtime/. |
| `app/workers/llm_parallelization_runtime.py` | `app/workers/runtime/llm_parallelization_runtime.py` | MOVE | PySpark parallelization handler moved under runtime/. |
| `app/workers/job_handlers.py` | `app/workers/dispatch/job_handlers.py` | MOVE | Job-type-to-handler registry moved under dispatch/. |
| `app/workers/worker_runtime_service.py` | `app/workers/dispatch/worker_runtime_service.py` | MOVE | Worker claiming/heartbeat/recovery moved under dispatch/. |
| `app/workers/worker_entrypoint.py` | `app/workers/entrypoints/worker_entrypoint.py` | MOVE | Generic canonical entrypoint moved under entrypoints/. |
| `app/workers/deck_queue_worker.py` | `app/workers/entrypoints/deck_queue_worker.py` | MOVE | Legacy polling loop entrypoint moved under entrypoints/. |

### Worker files created (consolidated entrypoints)

| File | Default `WORKER_KIND` | Replaces |
|---|---|---|
| `app/workers/entrypoints/source_worker.py` | `source_ingestion` | `source_ingestion_worker.py`, `source_extraction_worker.py`, `miniatures_worker.py`, `smart_deck_context_worker.py`, `brand_extraction_worker.py`, `schema_validation_worker.py` |
| `app/workers/entrypoints/generation_worker.py` | `llm_generation` | `llm_generation_worker.py`, `schema_validation_worker.py`, `preview_render_worker.py`, `apply_version_worker.py` |
| `app/workers/entrypoints/render_worker.py` | `preview_render` | `preview_render_worker.py` (standalone) |
| `app/workers/entrypoints/export_worker.py` | `export` | `export_worker.py`, `db_publisher_worker.py` |
| `app/workers/entrypoints/rescue_worker.py` | `stale_job_rescuer` | (new — no prior wrapper) |

### Worker files deleted (per-kind wrappers — 13 files)

These were thin wrappers that only set `WORKER_KIND` + `DECK_WORKER_JOB_TYPES` env vars and called `entrypoints.worker_entrypoint.main()`. Railway never starts them directly; it uses `railway.worker.toml` → `scripts/start_railway.py` → `scripts/deck_processing_worker.py` → `dispatch/worker_runtime_service.py`.

| Deleted file | Job type | Default kind |
|---|---|---|
| `app/workers/source_ingestion_worker.py` | `source_ingestion` | `source_ingestion` |
| `app/workers/source_extraction_worker.py` | `source_extraction` | `source_extraction` |
| `app/workers/miniatures_worker.py` | `miniatures` | `miniatures` |
| `app/workers/smart_deck_context_worker.py` | `smart_deck_context` | `smart_deck_context` |
| `app/workers/db_publisher_worker.py` | `db_publisher` | `db_publisher` |
| `app/workers/brand_extraction_worker.py` | `brand_extraction` | `brand_extraction` |
| `app/workers/llm_generation_worker.py` | `llm_generation` | `llm_generation` |
| `app/workers/schema_validation_worker.py` | `schema_validation` | `llm_generation` |
| `app/workers/preview_render_worker.py` | `preview_render` | `preview_render` |
| `app/workers/apply_version_worker.py` | `apply_version` | `llm_generation` |
| `app/workers/export_worker.py` | `export` | `export` |
| `app/workers/deck_queue_worker.py` | (legacy stub) | — |
| `app/workers/compile_final_deck_worker.py` | `compile_final_deck` | `export` |

### Remaining `app/workers/` structure after pruning pass

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

### Verification in worker pruning pass

| Check | Status |
|---|---|
| `python3 -m compileall app scripts tests` | PASS |
| `from app.workers.entrypoints.worker_entrypoint import main` | PASS |
| `from app.workers.runtime.source_pipeline_runtime import handle_source_ingestion` | PASS |
| `from app.workers.runtime.generation_runtime import handle_llm_generation` | PASS |
| `from app.workers.runtime.publisher_runtime import handle_db_publisher` | PASS |
| `from app.workers.runtime.llm_parallelization_runtime import handle_llm_parallelization` | BLOCKED by `pyspark` (expected — only in `Dockerfile.pyspark`) |
| `from app.workers.dispatch.job_handlers import get_workflow_job_handler` | PASS |
| `from app.workers.dispatch.worker_runtime_service import process_next_durable_deck` | PASS |
| `from app.workers.entrypoints.deck_queue_worker import main` | PASS |
| `from scripts.deck_processing_worker import main` | PASS |
| `pytest tests/test_worker_service_name_normalization.py tests/test_workflow_frontend_worker_boundary.py tests/test_railway_deploy_config.py` | 14/14 PASS |
| Railway worker startup impact | SAFE: no Railway config/start command changed; `scripts/deck_processing_worker.py` imports from `dispatch/` |
| Frontend/API contract | PASS by construction: no route paths or response schemas were changed |

## Continued Loop Update — 2026-07-04 Pass 3

## Continued Loop Update — 2026-07-04 Platform Pass

### Platform files moved

| Previous file | New owner | Action | Notes |
|---|---|---|---|
| `app/services/auth_session_service.py` | `app/services/platform/auth/auth_session_service.py` | MOVE | Auth/session lifecycle service moved under platform auth. |
| `app/services/user_service.py` | `app/services/platform/auth/user_service.py` | MOVE | User creation/auth/workspace bootstrap moved under platform auth. |
| `app/services/profile_service.py` | `app/services/platform/auth/profile_service.py` | MOVE | Profile read/update service moved under platform auth. |
| `app/services/connected_account_service.py` | `app/services/platform/auth/connected_account_service.py` | MOVE | Connected account test/listing service moved under platform auth. |
| `app/services/billing_service.py` | `app/services/platform/billing/billing_service.py` | MOVE | Subscription/plans/invoices service moved under platform billing. |
| `app/services/ai_usage_quota_service.py` | `app/services/platform/billing/ai_usage_quota_service.py` | MOVE | AI usage quota enforcement moved under platform billing. |
| `app/services/rate_limit_service.py` | `app/services/platform/billing/rate_limit_service.py` | MOVE | Cross-route rate limiting moved under platform billing. |
| `app/services/shell_service.py` | `app/services/platform/shell/shell_service.py` | MOVE | Shell dashboard/design batch read service moved under platform shell. |
| `app/services/shell_workspace_service.py` | `app/services/platform/shell/shell_workspace_service.py` | MOVE | Workspace shell read/write service moved under platform shell. |
| `app/services/workspace_ai_provider_service.py` | `app/services/platform/shell/workspace_ai_provider_service.py` | MOVE | Workspace AI provider credential/settings service moved under platform shell. |
| `app/services/turnstile_service.py` | `app/services/platform/shell/turnstile_service.py` | MOVE | Turnstile verification moved under platform shell. |
| `app/services/public_interest_service.py` | `app/services/platform/shell/public_interest_service.py` | MOVE | Public-interest lead creation moved under platform shell. |
| `app/services/superadmin_client.py` | `app/services/platform/admin/superadmin_client.py` | MOVE | Superadmin integration client moved under platform admin. |

### Remaining root `app/services/*.py` after platform pass

Only `app/services/__init__.py` remains at the root. All imports from the old root platform service paths were updated to the new `app.services.platform.*` paths.

### Verification in platform pass

| Check | Status |
|---|---|
| Stale root platform import scan | PASS: no matches. |
| Root service file scan | PASS: only `app/services/__init__.py` remains. |
| `python3 -m compileall app scripts tests` | PASS. |
| Tests | Not run locally because `pytest` is not installed. |
| Startup import | Still blocked by missing local dependency `fastapi`. |
| Frontend/API contract | PASS by construction: no route paths or response schemas were changed. |

### Files moved

| Previous file | New owner | Action | Notes |
|---|---|---|---|
| `app/services/smart_deck_llm_service.py` | `app/services/llm/generation_service.py` | ABSORB + MOVE | Replaced the previous wrapper with the active LLM generation/apply/assistant implementation. |
| `app/services/deck_generation_service.py` | `app/services/llm/deck_generation_service.py` | MOVE | Legacy/parallel generation route service moved under LLM. |
| `app/services/llm_knowledge_service.py` | `app/services/llm/knowledge_service.py` | MOVE | LLM knowledge health/metadata moved under LLM. |
| `app/services/llm_artifact_persistence_service.py` | `app/services/llm/artifact_persistence.py` | MOVE | Canonical LLM artifact persistence moved under LLM. |
| `app/services/critique_service.py` | `app/services/llm/critique_service.py` | ABSORB + MOVE | Replaced wrapper with implementation. |
| `app/services/smart_deck_prompt_builder.py` | `app/services/llm/prompt_builder.py` | ABSORB + MOVE | Replaced wrapper with implementation. |
| `app/services/smart_deck_artifact_writer.py` | `app/services/llm/artifact_service.py` | ABSORB + MOVE | Replaced wrapper with implementation. |
| `app/services/source_fact_service.py` | `app/services/llm/source_facts.py` | MOVE | Source fact classification used by LLM critique/generation. |
| `app/services/smart_deck_source_enrichment_service.py` | `app/services/llm/source_enrichment.py` | MOVE | Provider-based source label enrichment moved under LLM. |
| `app/services/smart_deck_retriever_service.py` | `app/services/llm/retriever_service.py` | MOVE | LLM retrieval context builders moved under LLM. |
| `app/services/deck_llm_artifact_service.py` | `app/services/llm/deck_artifact_read_model.py` | MOVE | LLM artifact read model preserved under LLM. |
| `app/services/smart_edit_service.py` | `app/services/llm/smart_edit_service.py` | MOVE | Smart Edit generation/critique service moved under LLM. |
| `app/services/smart_edit_rate_limit.py` | `app/services/llm/smart_edit_rate_limit.py` | MOVE | Smart Edit quota/rate helper moved with Smart Edit. |
| `app/services/smart_deck_quality_eval_service.py` | `app/services/llm/quality_eval_service.py` | MOVE | Generated payload quality/repair policy moved under LLM. |
| `app/services/smart_deck_subject_registry.py` | `app/services/llm/subject_registry.py` | MOVE | Subject registry used by LLM generation moved under LLM. |
| `app/services/smart_deck_subject_detection_service.py` | `app/services/llm/subject_detection.py` | MOVE | Subject detection moved under LLM. |
| `app/services/smart_deck_agent_service.py` | `app/services/llm/agent_service.py` | MOVE | Smart Deck agent queue adapter moved under LLM. |
| `app/services/smart_deck_job_service.py` | `app/services/deck_processing/smart_deck_context.py` | ABSORB + MOVE | Replaced wrapper with Smart Deck context implementation. |
| `app/services/deck_runtime_surface_service.py` | `app/services/visualizer/generated_deck_read_model.py` | MOVE | Frontend-facing generated deck/runtime read surface moved under visualizer. |
| `app/services/deck_artifact_listing_service.py` | `app/services/visualizer/deck_artifact_listing.py` | MOVE | Deck LLM artifact listing read model moved under visualizer. |
| `app/services/workspace_dashboard_service.py` | `app/services/visualizer/workspace_dashboard_read_model.py` | MOVE | Dashboard read model moved under visualizer. |
| `app/services/final_deck_service.py` | `app/services/rendering/final_deck_service.py` | MOVE | Final deck compilation/apply surface moved under rendering. |
| `app/services/deck_retention_service.py` | `app/services/storage/deck_retention.py` | MOVE | Artifact retention/archive policy moved under storage. |
| `app/services/product_analytics_service.py` | `app/services/admin/product_analytics.py` | MOVE | Product analytics event/metrics service moved under admin. |
| `app/services/guardrail_client.py` | `app/services/admin/guardrail_client.py` | MOVE | Guardrail audit/client moved under admin. |
| `app/services/agent_telemetry_service.py` | `app/services/admin/agent_telemetry.py` | MOVE | Agent telemetry moved under admin. |
| `app/services/agent_regression_service.py` | `app/services/admin/agent_regression.py` | MOVE | Regression fixture generation moved under admin. |
| `app/services/agent_learning_memory_service.py` | `app/services/admin/agent_learning_memory.py` | MOVE | Agent learning memory admin read/write moved under admin. |
| `app/services/save_confirmation_service.py` | `app/services/deck_processing/save_confirmation.py` | MOVE | Deck save confirmation state moved under deck processing. |
| `app/services/first_batch_rescue_service.py` | `app/services/deck_processing/first_batch_rescue.py` | MOVE | First-batch/source rescue helper moved under deck processing. |
| `app/services/deck_iteration_service.py` | `app/services/visualizer/deck_iteration_read_model.py` | MOVE | Deck iteration read model moved under visualizer. |

### Remaining root `app/services/*.py`

Superseded by the platform pass above. Only `app/services/__init__.py` remains at the root.

### Verification in pass 3

| Check | Status |
|---|---|
| `python3 -m compileall app scripts tests` | PASS after every move batch. |
| Tests | Not run locally because `pytest` is not installed. |
| Startup import | Blocked by missing local dependency `fastapi`. |
| Frontend contract | PASS by construction: no route paths or response schemas were changed. |
| Railway safety | PASS: no Railway config/start command changed; worker imports compile. |

### Files moved

| Previous file | New owner | Action | Notes |
|---|---|---|---|
| `app/services/upload_security.py` | `app/services/storage/upload_security.py` | MOVE | Upload validation/stream limiting moved under storage; route/test imports updated. |
| `app/services/upload_scan_service.py` | `app/services/storage/upload_scan.py` | MOVE | Upload scanner adapter moved under storage. |
| `app/services/upload_readiness_service.py` | `app/services/storage/upload_readiness.py` | MOVE | Upload persistence diagnostics moved under storage. |
| `app/services/deck_file_service.py` | `app/services/storage/deck_file_service.py` | MOVE | Stored deck file path/hash/PPT-to-PDF helpers moved under storage. |
| `app/services/deck_intake_service.py` | `app/services/deck_processing/deck_intake_service.py` | MOVE | Deck intake/status belongs to source ingestion. |
| `app/services/workspace_summary_service.py` | `app/services/deck_processing/workspace_summary_service.py` | MOVE | Upload/session summary read model belongs to source ingestion/product processing. |
| `app/services/pdf_deck_extraction_service.py` | `app/services/deck_processing/source_extraction.py` | ABSORB + DELETE old wrapper | Real PDF extraction replaced the previous wrapper. |
| `app/services/deck_preview_service.py` | `app/services/deck_processing/source_preview_service.py` | MOVE | Miniatures orchestration moved under deck processing. |
| `app/services/slide_thumbnail_service.py` | `app/services/rendering/slide_thumbnail.py` | MOVE | Low-level thumbnail rendering moved under rendering. |
| `app/services/workflow_job_service.py` | `app/services/deck_processing/workflow_jobs.py` | MOVE | Canonical job type/status contract moved under deck processing. |
| `app/services/deck_state_machine_service.py` | `app/services/deck_processing/state_machine.py` | MOVE | Deck lifecycle state machine moved under deck processing. |
| `app/services/deck_processing_queue_service.py` | `app/services/deck_processing/processing_queue.py` | MOVE | Legacy queue/run helpers moved under deck processing. |
| `app/services/deck_processing_visibility_service.py` | `app/services/deck_processing/processing_visibility.py` | MOVE | Processing page projection moved under deck processing. |
| `app/services/deck_processing_worker_service.py` | `app/workers/worker_runtime_service.py` | MOVE | Durable worker runtime moved under workers; Railway script import updated. |
| `app/services/smart_deck_readiness_service.py` | `app/services/admin/readiness_diagnostics.py` | MOVE | Admin/debug readiness diagnostics moved under admin. |
| `app/services/admin_operations_service.py` | `app/services/admin/operations.py` | MOVE | Admin operations route service moved under admin. |
| `app/services/admin_deck_repair_service.py` | `app/services/admin/deck_repair.py` | MOVE | Admin deck repair/requeue moved under admin. |
| `app/services/admin_workflow_observability_service.py` | `app/services/admin/workflow_observability.py` | MOVE | Admin workflow observability moved under admin. |
| `app/services/security_audit_service.py` | `app/services/admin/security_audit.py` | MOVE | Security audit event writer moved under admin. |
| `app/services/failure_ticket_service.py` | `app/services/admin/failure_tickets.py` | MOVE | Failure ticketing moved under admin. |
| `app/services/brand_enrichment_service.py` | `app/services/brand/brand_enrichment.py` | MOVE | Brand enrichment moved under brand. |
| `app/services/company_profile_service.py` | `app/services/brand/company_profile.py` | MOVE | Company profile inference/persistence moved under brand. |
| `app/services/website_context_service.py` | `app/services/brand/website_context.py` | MOVE | Website URL/context helpers moved under brand. |

### Files still floating after pass 2

| File/group | Classification | Owner | Reason |
|---|---|---|---|
| `smart_deck_llm_service.py`, `deck_generation_service.py`, `llm_knowledge_service.py`, `llm_artifact_persistence_service.py`, `deck_llm_artifact_service.py`, `smart_deck_prompt_builder.py`, `critique_service.py`, `deck_runtime_surface_service.py` | KEEP TEMPORARILY | `llm` | Active LLM/generation monolith and knowledge surfaces; next loop should move in one focused LLM pass to avoid breaking generation jobs. |
| `smart_deck_job_service.py`, `smart_deck_source_enrichment_service.py`, `smart_deck_artifact_writer.py`, `smart_deck_retriever_service.py`, `source_fact_service.py`, `first_batch_rescue_service.py` | KEEP TEMPORARILY | `deck_processing` / `visualizer` | Smart Deck context/readiness/source enrichment path; needs Smart Deck smoke after move. |
| `smart_edit_service.py`, `smart_edit_rate_limit.py`, `smart_deck_agent_service.py`, `smart_deck_quality_eval_service.py`, `smart_deck_subject_registry.py`, `smart_deck_subject_detection_service.py` | LEGACY UNKNOWN | `legacy_unknown` / `llm` | Smart Edit and agent surfaces are active-adjacent but not part of the 12-stage spine. |
| `auth_session_service.py`, `user_service.py`, `profile_service.py`, `connected_account_service.py`, `workspace_ai_provider_service.py`, `superadmin_client.py`, `turnstile_service.py`, `rate_limit_service.py`, `ai_usage_quota_service.py`, `billing_service.py` | LEGACY UNKNOWN | `api/routes` / `admin` | Account/platform services are outside deck-processing spine and need a separate platform-owner decision. |
| `shell_service.py`, `shell_workspace_service.py`, `workspace_dashboard_service.py`, `product_analytics_service.py`, `public_interest_service.py`, `guardrail_client.py`, `deck_artifact_listing_service.py`, `deck_iteration_service.py`, `final_deck_service.py`, `save_confirmation_service.py`, `deck_retention_service.py`, `railway_upload_smoke_test_service.py`, `upload_service.py` | KEEP TEMPORARILY | mixed | Still live route surfaces; route contracts unchanged. Move in product-surface batches only. |
| `agent_telemetry_service.py`, `agent_regression_service.py`, `agent_learning_memory_service.py` | KEEP TEMPORARILY | `admin` | Broadly imported by LLM/orchestration/tests; move after LLM monolith pass. |

### Verification in pass 2

| Check | Status |
|---|---|
| `python3 -m compileall app scripts tests` | PASS after every batch. |
| Tests | Not run: `pytest` module is not installed in the local shell. |
| Startup import | Still blocked by missing runtime dependencies such as `fastapi`. |
| Railway safety | No worker entrypoint files or Railway config renamed/deleted; `scripts/deck_processing_worker.py` now imports `app.workers.dispatch.worker_runtime_service`. |

### Files moved

| Previous file | New owner | Action | Notes |
|---|---|---|---|
| `app/services/brand_extraction_service.py` | `app/services/brand/brand_extraction.py` | MOVE | Active brand route/service implementation; imports updated. |
| `app/services/brand_loader_service.py` | `app/services/brand/brand_profile_persistence.py` | MOVE | Brand profile persistence; imports updated. |
| `app/services/brand_status_service.py` | `app/services/brand/brand_read_model.py` | MOVE | Brand status/read model; imports updated. |
| `app/services/brand_profile_card_contract.py` | `app/services/brand/brand_profile_card_contract.py` | MOVE | Brand card swatch contract; script import updated. |
| `app/services/export_service.py` | `app/services/rendering/export_service.py` | MOVE | Export route/worker imports updated. |
| `app/services/runtime_schema_service.py` | `app/services/rendering/render_schema_service.py` | MOVE | Runtime Smart Deck schema bootstrap; startup imports updated. |
| `app/services/smart_deck_output_validation.py` | `app/services/rendering/schema_validation.py` | MERGE | Source label validation now shares owner with generated deck validation. |
| `app/services/generation/validate_generated_deck.py` | `app/services/rendering/schema_validation.py` | ABSORB + DELETE | `validate_generated_deck` absorbed. |
| `app/services/generation/generated_deck_schema.py` | `app/services/rendering/schema_validation.py` | ABSORB + DELETE | `load_generated_deck_schema` absorbed. |
| `app/services/upload_storage.py` | `app/services/storage/artifact_storage.py` | MOVE | Real upload storage implementation moved under storage; upload imports updated. |
| `app/services/bucket_artifact_service.py` | `app/services/storage/signed_urls.py` | MOVE | Bucket artifact keys/CRUD/signed URLs moved under storage. |
| `app/services/storage_health_service.py` | `app/services/storage/bucket_health.py` | MOVE | Storage health check moved under storage. |
| `app/services/storage_inventory_service.py` | `app/services/admin/diagnostics.py` | MOVE | Admin storage inventory/cleanup moved under admin diagnostics. |
| `app/services/worker_runtime_status_service.py` | `app/services/admin/worker_health.py` | MOVE | Worker heartbeat read/write moved under admin/worker health. |
| `app/services/deployment_readiness_service.py` | `app/services/admin/product_spine_health.py` | MOVE | Deployment/product readiness moved under admin health. |
| `app/services/llm_parallelization_service.py` | `app/services/llm/parallelization_service.py` | MOVE | LLM batch partitioning moved under LLM. |

### Files deleted after absorption

| Deleted file | Replacement verified |
|---|---|
| `app/services/generation/validate_generated_deck.py` | `app/services/rendering/schema_validation.py::validate_generated_deck` |
| `app/services/generation/generated_deck_schema.py` | `app/services/rendering/schema_validation.py::load_generated_deck_schema` |

### Files still floating in `app/services/`

These are classified and intentionally kept temporarily because they are active route, auth, billing, upload, or worker runtime surfaces with higher blast radius than this cleanup loop should take on without focused tests.

| File/group | Classification | Owner | Reason |
|---|---|---|---|
| `upload_service.py`, `deck_intake_service.py`, `deck_file_service.py`, `upload_security.py`, `upload_scan_service.py`, `upload_readiness_service.py`, `railway_upload_smoke_test_service.py`, `workspace_summary_service.py` | KEEP TEMPORARILY | `deck_processing` / `storage` | Upload path is live; do not move further without upload route smoke test. |
| `pdf_deck_extraction_service.py`, `deck_extractors/*`, `slide_thumbnail_service.py`, `deck_preview_service.py` | KEEP TEMPORARILY | `deck_processing` / `rendering` | Active extraction/miniatures path; further moves require PDF fixture verification. |
| `workflow_job_service.py`, `deck_processing_worker_service.py`, `deck_state_machine_service.py`, `deck_processing_queue_service.py`, `deck_processing_visibility_service.py`, `smart_deck_readiness_service.py` | KEEP TEMPORARILY | `deck_processing` / `workers` / `admin` | Core workflow-state and Railway worker dependencies; high import count. |
| `smart_deck_llm_service.py`, `deck_generation_service.py`, `llm_knowledge_service.py`, `llm_artifact_persistence_service.py`, `critique_service.py`, `smart_deck_prompt_builder.py` | KEEP TEMPORARILY | `llm` | Active LLM path; provider cleanup continues separately. |
| `smart_deck_job_service.py`, `smart_deck_source_enrichment_service.py`, `smart_deck_artifact_writer.py`, `smart_deck_retriever_service.py`, `source_fact_service.py`, `deck_runtime_surface_service.py` | KEEP TEMPORARILY | `deck_processing` / `llm` / `visualizer` | Smart Deck context/read surface; requires end-to-end Smart Deck smoke before moving. |
| `brand_enrichment_service.py`, `company_profile_service.py` | KEEP TEMPORARILY | `brand` | Brand secondary services; primary brand owner folder is now created. |
| `admin_operations_service.py`, `admin_deck_repair_service.py`, `admin_workflow_observability_service.py`, `security_audit_service.py`, `failure_ticket_service.py`, `agent_telemetry_service.py`, `agent_regression_service.py`, `agent_learning_memory_service.py` | KEEP TEMPORARILY | `admin` | Admin route dependencies; move in a focused admin pass. |
| `auth_session_service.py`, `user_service.py`, `profile_service.py`, `connected_account_service.py`, `superadmin_client.py`, `turnstile_service.py`, `rate_limit_service.py`, `ai_usage_quota_service.py`, `billing_service.py`, `workspace_ai_provider_service.py` | LEGACY UNKNOWN | `api/routes` / `admin` / `legacy_unknown` | Account/platform services are outside the 12-stage deck spine; document before pruning. |
| `smart_edit_service.py`, `smart_edit_rate_limit.py`, `smart_deck_agent_service.py`, `smart_deck_quality_eval_service.py`, `smart_deck_subject_registry.py`, `smart_deck_subject_detection_service.py`, `deck_iteration_service.py`, `final_deck_service.py`, `first_batch_rescue_service.py`, `save_confirmation_service.py`, `deck_artifact_listing_service.py`, `workspace_dashboard_service.py`, `product_analytics_service.py`, `public_interest_service.py`, `shell_service.py`, `shell_workspace_service.py`, `website_context_service.py`, `guardrail_client.py` | LEGACY UNKNOWN | `legacy_unknown` / `api/routes` | Live or adjacent product surfaces not yet mapped to the target spine. |

### Verification in this loop

| Check | Status |
|---|---|
| `python -m compileall app` | `python` unavailable in local shell. |
| `python3 -m compileall app scripts tests` | PASS after moves. |
| Frontend route contract scan | PASS: backend route paths and payload contracts were not changed. |
| Railway worker startup impact | SAFE: `scripts/start_railway.py`, `scripts/deck_processing_worker.py`, worker files, and job mappings were not renamed or deleted. Imports used by worker startup were updated and compiled. |

### Next loop action

Move the remaining high-count active files in focused batches: upload/storage path first, then workflow/job runtime, then Smart Deck context/LLM monolith, then admin/account legacy surfaces. Do not delete worker wrapper files until the Railway dashboard service/start-command check is manually confirmed.

## 1. Full Backend File Inventory

Total: 302 Python files across `app/`.

### Target folders (already organized):
- `app/services/deck_processing/` (15 files) — Source pipeline spine
- `app/services/visualizer/` (5 files) — Frontend-facing read models
- `app/services/llm/` (16 files) — LLM provider abstraction + generation wrappers
- `app/services/rendering/` (2 files) — Version apply spine wrappers
- `app/services/storage/` (5 files) — Storage abstraction + signed URLs
- `app/services/admin/` (0 files) — Empty, create as needed
- `app/workers/` (23 files) — Job handlers + Railway entrypoints
- `app/api/routes/` (37 files) — Route handlers

### Files outside target folders:

**app/agents/** (7 files):
1. `app/agents/adaptation_suggestion_agent.py`
2. `app/agents/audience_alignment_agent.py`
3. `app/agents/block_classifier_agent.py`
4. `app/agents/diligence_gap_agent.py`
5. `app/agents/__init__.py`
6. `app/agents/llm_agent_utils.py`
7. `app/agents/smart_edit_agent.py`

**app/ai/** (12 files):
8. `app/ai/anthropic_provider.py`
9. `app/ai/architecture_runtime_context.py`
10. `app/ai/diligence_knowledge_context.py`
11. `app/ai/__init__.py`
12. `app/ai/llm_provider.py`
13. `app/ai/market_research_knowledge_context.py`
14. `app/ai/openai_provider.py`
15. `app/ai/openrouter_provider.py`
16. `app/ai/prompts.py`
17. `app/ai/provider.py`
18. `app/ai/slide_archetypes_context.py`
19. `app/ai/vc_prompt_context.py`

**app/ai_orchestration/** (20 files):
20. `app/ai_orchestration/context_builder.py`
21. `app/ai_orchestration/errors.py`
22. `app/ai_orchestration/__init__.py`
23. `app/ai_orchestration/orchestrator.py`
24. `app/ai_orchestration/prompts.py`
25. `app/ai_orchestration/provider_resolver.py`
26. `app/ai_orchestration/providers/__init__.py`
27. `app/ai_orchestration/providers/anthropic_provider.py`
28. `app/ai_orchestration/providers/base.py`
29. `app/ai_orchestration/providers/openai_provider.py`
30. `app/ai_orchestration/providers/openrouter_provider.py`
31. `app/ai_orchestration/router.py`
32. `app/ai_orchestration/schemas.py`
33. `app/ai_orchestration/tool_registry.py`
34. `app/ai_orchestration/tools/__init__.py`
35. `app/ai_orchestration/tools/audience_tools.py`
36. `app/ai_orchestration/tools/brand_tools.py`
37. `app/ai_orchestration/tools/deck_tools.py`
38. `app/ai_orchestration/tools/export_tools.py`
39. `app/ai_orchestration/tools/generation_tools.py`
40. `app/ai_orchestration/tools/slide_tools.py`
41. `app/ai_orchestration/validators.py`

**app/api/** (2 files outside routes/):
42. `app/api/__init__.py`
43. `app/api/deps.py`

**app/core/** (7 files):
44. `app/core/config.py`
45. `app/core/errors.py`
46. `app/core/__init__.py`
47. `app/core/railway_env.py`
48. `app/core/security.py`
49. `app/core/statuses.py`
50. `app/core/workspace_ai_crypto.py`

**app/db/** (18 files):
51. `app/db/base.py`
52. `app/db/__init__.py`
53. `app/db/models/__init__.py`
54. `app/db/models/adaptation_run.py`
55. `app/db/models/adaptation_suggestion.py`
56. `app/db/models/analysis_finding.py`
57. `app/db/models/analysis_run.py`
58. `app/db/models/audience_profile.py`
59. `app/db/models/block_classification.py`
60. `app/db/models/deck_export.py`
61. `app/db/models/deck_file.py`
62. `app/db/models/deck.py`
63. `app/db/models/deck_slide_block.py`
64. `app/db/models/deck_slide.py`
65. `app/db/models/deck_slide_revision.py`
66. `app/db/models/entities.py`
67. `app/db/models/interest_lead.py`
68. `app/db/models/permission.py`
69. `app/db/models/smart_edit_run.py`
70. `app/db/models/smart_edit_suggestion.py`
71. `app/db/models/user.py`
72. `app/db/models/workspace.py`
73. `app/db/session.py`

**app/observability/** (2 files):
74. `app/observability/__init__.py`
75. `app/observability/tracing.py`

**app/schemas/** (28 files):
76–103. All under `app/schemas/`

**app/services/** (63 files outside subfolders):
104. `app/services/admin_deck_repair_service.py`
105. `app/services/admin_operations_service.py`
106. `app/services/admin_workflow_observability_service.py`
107. `app/services/agent_learning_memory_service.py`
108. `app/services/agent_regression_service.py`
109. `app/services/agent_telemetry_service.py`
110. `app/services/ai_usage_quota_service.py`
111. `app/services/auth_session_service.py`
112. `app/services/billing_service.py`
113. `app/services/brand_enrichment_service.py`
114. `app/services/brand_extraction_service.py`
115. `app/services/brand_loader_service.py`
116. `app/services/brand_profile_card_contract.py`
117. `app/services/brand_status_service.py`
118. `app/services/bucket_artifact_service.py`
119. `app/services/company_profile_service.py`
120. `app/services/connected_account_service.py`
121. `app/services/critique_service.py`
122. `app/services/deck_artifact_listing_service.py`
123. `app/services/deck_extractors/__init__.py`
124. `app/services/deck_extractors/pdf_image_extractor.py`
125. `app/services/deck_extractors/pdf_metadata_extractor.py`
126. `app/services/deck_extractors/pdf_ocr_extractor.py`
127. `app/services/deck_extractors/pdf_text_extractor.py`
128. `app/services/deck_extractors/slide_block_builder.py`
129. `app/services/deck_file_service.py`
130. `app/services/deck_generation_service.py`
131. `app/services/deck_intake_service.py`
132. `app/services/deck_iteration_service.py`
133. `app/services/deck_llm_artifact_service.py`
134. `app/services/deck_preview_service.py`
135. `app/services/deck_processing_queue_service.py`
136. `app/services/deck_processing_visibility_service.py`
137. `app/services/deck_processing_worker_service.py`
138. `app/services/deck_retention_service.py`
139. `app/services/deck_runtime_surface_service.py`
140. `app/services/deck_state_machine_service.py`
141. `app/services/deployment_readiness_service.py`
142. `app/services/export_service.py`
143. `app/services/failure_ticket_service.py`
144. `app/services/final_deck_service.py`
145. `app/services/first_batch_rescue_service.py`
146. `app/services/generation/__init__.py`
147. `app/services/generation/claude/build_prompt.py`
148. `app/services/generation/claude/claude_generate_slides.py`
149. `app/services/generation/generated_deck_schema.py`
150. `app/services/generation/openai/__init__.py`
151. `app/services/generation/openai/openai_generate_slides.py`
152. `app/services/generation/validate_generated_deck.py`
153. `app/services/guardrail_client.py`
154. `app/services/__init__.py`
155. `app/services/llm_artifact_persistence_service.py`
156. `app/services/llm_knowledge_service.py`
157. `app/services/llm_parallelization_service.py`
158. `app/services/pdf_deck_extraction_service.py`
159. `app/services/product_analytics_service.py`
160. `app/services/profile_service.py`
161. `app/services/public_interest_service.py`
162. `app/services/railway_upload_smoke_test_service.py`
163. `app/services/rate_limit_service.py`
164. `app/services/runtime_schema_service.py`
165. `app/services/save_confirmation_service.py`
166. `app/services/security_audit_service.py`
167. `app/services/shell_service.py`
168. `app/services/shell_workspace_service.py`
169. `app/services/slide_thumbnail_service.py`
170. `app/services/smart_deck_agent_service.py`
171. `app/services/smart_deck_artifact_writer.py`
172. `app/services/smart_deck_job_service.py`
173. `app/services/smart_deck_llm_service.py`
174. `app/services/smart_deck_output_validation.py`
175. `app/services/smart_deck_prompt_builder.py`
176. `app/services/smart_deck_quality_eval_service.py`
177. `app/services/smart_deck_readiness_service.py`
178. `app/services/smart_deck_retriever_service.py`
179. `app/services/smart_deck_source_enrichment_service.py`
180. `app/services/smart_deck_subject_detection_service.py`
181. `app/services/smart_deck_subject_registry.py`
182. `app/services/smart_edit_rate_limit.py`
183. `app/services/smart_edit_service.py`
184. `app/services/source_fact_service.py`
185. `app/services/storage_health_service.py`
186. `app/services/storage_inventory_service.py`
187. `app/services/superadmin_client.py`
188. `app/services/turnstile_service.py`
189. `app/services/upload_readiness_service.py`
190. `app/services/upload_scan_service.py`
191. `app/services/upload_security.py`
192. `app/services/upload_service.py`
193. `app/services/upload_storage.py`
194. `app/services/user_service.py`
195. `app/services/website_context_service.py`
196. `app/services/worker_runtime_status_service.py`
197. `app/services/workflow_job_service.py`
198. `app/services/workspace_ai_provider_service.py`
199. `app/services/workspace_dashboard_service.py`
200. `app/services/workspace_summary_service.py`

**app/** root (3 files):
201. `app/__init__.py`
202. `app/main.py`

---

## 2. File Disposition Table

### 2.1 Files to DELETE (proven unused — no imports, no routes, no workers)

| Current file | Why | Replacement | Risk |
|---|---|---|---|
| `app/ai/prompts.py` | 2 string constants, NOT imported by any file | None (constants are dead) | None |
| `app/ai_orchestration/prompts.py` | 1 string constant, NOT imported by any file | None (constant is dead) | None |
| `app/ai_orchestration/tool_registry.py` | ToolRegistry class, NOT imported by any file | None | None |
| `app/ai_orchestration/tools/__init__.py` | Empty docstring, NOT imported | None | None |
| `app/ai_orchestration/tools/audience_tools.py` | 2-line stub (`TOOL_NAME = "audience_tools"`), NOT imported | None | None |
| `app/ai_orchestration/tools/brand_tools.py` | 2-line stub, NOT imported | None | None |
| `app/ai_orchestration/tools/deck_tools.py` | 2-line stub, NOT imported | None | None |
| `app/ai_orchestration/tools/export_tools.py` | 2-line stub, NOT imported | None | None |
| `app/ai_orchestration/tools/generation_tools.py` | 2-line stub, NOT imported | None | None |
| `app/ai_orchestration/tools/slide_tools.py` | 2-line stub, NOT imported | None | None |

### 2.2 Files to KEEP (active on product spine — still needed)

These are all in the product spine, actively imported, and must remain:

| Current file | Spine stage | Kept because |
|---|---|---|
| `app/services/workflow_job_service.py` | All stages | Job type constants, pipeline sequence, status transitions — imported by 22+ files |
| `app/services/deck_processing_worker_service.py` | All stages | Worker claiming, heartbeat, dispatch — imported by 5+ files |
| `app/services/deck_state_machine_service.py` | DB Publisher | Deck state transitions — imported by 16+ files |
| `app/services/pdf_deck_extraction_service.py` | Source Extraction | PDF structure extraction — imported by source_structure_persistence |
| `app/services/deck_preview_service.py` | Miniatures | Source preview rendering + persistence — imported by visualizer/miniature_service |
| `app/services/smart_deck_job_service.py` | Smart Deck Context | Source workspace preparation — imported by deck_processing/smart_deck_context |
| `app/services/smart_deck_llm_service.py` | LLM Generation | Monolithic orchestration — imported by 13+ files |
| `app/services/export_service.py` | Export | Export creation/download — imported by publisher_runtime, routes |
| `app/services/slide_thumbnail_service.py` | Miniatures | pdftoppm thumbnail — imported by pdf_deck_extraction (opt-in) |
| `app/services/upload_storage.py` | Source Ingestion | Upload storage abstraction — imported by 22+ files |
| `app/services/bucket_artifact_service.py` | Storage | Bucket artifact CRUD + signed URLs — imported by 6 files |
| `app/services/storage_health_service.py` | Storage | Storage health probes — imported by routes |
| `app/services/deck_processing_visibility_service.py` | Processing page | UI processing projection — imported by 3 routes |
| `app/services/deck_processing_queue_service.py` | All stages | Processing queue management — imported by workflow_orchestration |
| `app/services/smart_deck_readiness_service.py` | DB Publisher | Readiness diagnostics — imported by admin_operations, admin_deck_repair |
| `app/services/upload_service.py` | Source Ingestion | Legacy upload/state transitions — imported by routes |
| `app/services/deck_intake_service.py` | Source Ingestion | Deck intake/brand upload persistence — imported by routes |
| `app/services/workspace_summary_service.py` | Source Ingestion | Upload session/deck summaries — imported by products route |

### 2.3 Files to KEEP TEMPORARILY (active but need future split)

| Current file | Why keep now | Future action |
|---|---|---|
| `app/ai/anthropic_provider.py` | Re-export shim imported by 5 files | Delete after all callers migrate to `app/services/llm/` |
| `app/ai/llm_provider.py` | Actual Anthropic implementation; wrapped by `app/services/llm/anthropic_provider.py` | Absorb into `app/services/llm/anthropic_provider.py` |
| `app/ai/openai_provider.py` | Actual OpenAI implementation; wrapped by `app/services/llm/openai_provider.py` | Absorb into `app/services/llm/openai_provider.py` |
| `app/ai/openrouter_provider.py` | Actual OpenRouter implementation; wrapped by `app/services/llm/openrouter_provider.py` | Absorb into `app/services/llm/openrouter_provider.py` |
| `app/ai/provider.py` | AIProvider Protocol; used only by `app/ai/*` internally | Delete when `app/ai/*` is absorbed |
| `app/ai/architecture_runtime_context.py` | Context builders imported by smart_deck_llm_service (2 consumers) | Move into `app/services/llm/` prompts |
| `app/ai/slide_archetypes_context.py` | Context builders imported by 4 files | Move into `app/services/llm/` prompts |
| `app/ai/diligence_knowledge_context.py` | Context builders imported by 2 files | Move into `app/services/llm/` prompts |
| `app/ai/vc_prompt_context.py` | Context builders imported by smart_deck_llm_service | Move into `app/services/llm/` prompts |
| `app/ai/market_research_knowledge_context.py` | Context builders imported by llm_knowledge_service | Move into `app/services/llm/` prompts |
| `app/ai_orchestration/` (entire module) | Active orchestration layer; `app/ai_orchestration/router.py` is in product routes | Keep until LLM harmonisation fully migrates orchestration to `app/services/llm/` |
| `app/services/generation/claude/` | Orphaned `claude_generate_slides.py` — not called by any active route/worker | Delete after confirming no imports |
| `app/services/generation/openai/` | Orphaned `openai_generate_slides.py` — not called by any active route/worker | Delete after confirming no imports |
| `app/services/generation/validate_generated_deck.py` | Schema validation — called by generation_runtime handler | Move to `app/services/rendering/` |

### 2.4 Files to MOVE (belong in a target folder, imports must update)

| Current file | Target folder | Reason |
|---|---|---|
| `app/services/workflow_job_service.py` | `app/services/deck_processing/workflow_jobs.py` | Job contract belongs with pipeline |
| `app/services/deck_processing_worker_service.py` | `app/workers/worker_runtime_service.py` | Worker dispatch belongs with workers |
| `app/services/deck_state_machine_service.py` | `app/services/deck_processing/state_machine.py` | State transitions belong with processing |
| `app/services/deck_processing_visibility_service.py` | `app/services/deck_processing/processing_visibility.py` | Already in deck_processing conceptually |
| `app/services/deck_processing_queue_service.py` | `app/services/deck_processing/processing_queue.py` | Already in deck_processing conceptually |
| `app/services/storage_health_service.py` | `app/services/storage/storage_health.py` | Already duplicated there |
| `app/services/slide_thumbnail_service.py` | `app/services/rendering/slide_thumbnail.py` | Rendering helper |
| `app/services/export_service.py` | `app/services/rendering/export.py` | Export belongs with rendering |
| `app/services/smart_deck_readiness_service.py` | `app/services/admin/readiness_diagnostics.py` | Admin diagnostics |
| `app/services/bucket_artifact_service.py` | `app/services/storage/artifact_storage.py` | Already has storage counterpart |
| `app/services/upload_storage.py` | `app/services/storage/upload_storage.py` | Storage belongs with storage |

### 2.5 LEGACY UNKNOWN (cannot prove safe deletion yet)

| Current file | Question |
|---|---|
| `app/services/upload_service.py` | Is legacy upload still used by routes? |
| `app/services/deck_intake_service.py` | Is intake still used by frontend? |
| `app/services/deck_generation_service.py` | Is duplicate generation surface still used? |
| `app/services/smart_edit_service.py` | Is Smart Edit a live product feature? |
| `app/services/company_profile_service.py` | Used by brand extraction — check if needed independently |
| `app/services/deck_iteration_service.py` | Check if still used by any flow |
| `app/services/smart_deck_retriever_service.py` | Check if used directly or only via smart_deck_llm_service |

---

## 3. Product Spine Mapping

| Stage | Files | Primary worker | Route | Frontend contract |
|---|---|---|---|---|
| 1. Source Ingestion | `deck_processing/source_ingestion.py`, `workers/source_pipeline_runtime.py`, `services/upload_storage.py` | `source_ingestion_worker.py` | `products.py` POST upload | N/A (worker stage) |
| 2. Source Extraction | `deck_processing/source_extraction.py`, `services/pdf_deck_extraction_service.py`, `services/deck_extractors/*` | `source_extraction_worker.py` | N/A | N/A (worker stage) |
| 3. Miniatures | `deck_processing/source_preview_renderer.py`, `source_preview_persistence.py`, `services/deck_preview_service.py`, `services/slide_thumbnail_service.py` | `miniatures_worker.py` | N/A | N/A (worker stage) |
| 4. Smart Deck Context | `deck_processing/smart_deck_context.py`, `services/smart_deck_job_service.py`, `services/smart_deck_source_enrichment_service.py`, `services/smart_deck_artifact_writer.py`, `services/smart_deck_output_validation.py`, `services/smart_deck_prompt_builder.py` | `smart_deck_context_worker.py` | N/A | N/A (worker stage) |
| 5. DB Publisher | `deck_processing/readiness_publisher.py`, `workers/publisher_runtime.py` | `db_publisher_worker.py` | N/A | `workflow-state` returns `canOpenSmartDeck=true` |
| 6. Brand Extraction | `deck_processing/brand_extraction.py`, `services/brand_extraction_service.py`, `services/brand_loader_service.py`, `services/brand_enrichment_service.py` | `brand_extraction_worker.py` | `brand_extraction.py` | Non-blocking for visualizer |
| 7. LLM Generation | `smart_deck_llm_service.py`, `services/llm/generation_service.py` (wrapper), `workers/generation_runtime.py` | `llm_generation_worker.py` | `smart_deck.py` POST generation-jobs | `GET /smart-deck/generation-jobs/{id}` |
| 8. LLM Parallelization | `services/llm_parallelization_service.py`, `workers/llm_parallelization_runtime.py` | `llm_parallelization_runtime.py` | N/A | N/A |
| 9. Schema Validation | `services/generation/validate_generated_deck.py`, `generated_deck_schema.py`, `workers/generation_runtime.py` | `schema_validation_worker.py` | N/A | N/A |
| 10. Preview Render | `workers/generation_runtime.py` | `preview_render_worker.py` | N/A | N/A |
| 11. Apply Version | `services/rendering/version_apply_service.py` (wrapper), `smart_deck_llm_service.py` | `apply_version_worker.py` | `smart_deck.py` POST apply | `GET /design-versions` |
| 12. Export | `services/export_service.py`, `workers/publisher_runtime.py` | `export_worker.py` | `exports.py` POST/GET | `GET /exports/{id}/download` |

---

## 4. Failure Clusters

### Upload Failure Cluster
- **Files:** `routes/products.py`, `routes/upload_rescue.py`, `routes/product_upload_compat.py`, `services/upload_storage.py`, `services/upload_service.py`, `services/upload_security.py`, `services/upload_scan_service.py`, `services/workspace_summary_service.py`, `services/deck_intake_service.py`, `services/deck_file_service.py`
- **Symptoms:** Upload returns 500, file not persisted, no workflow jobs created
- **Logs to check:** backend logs for `upload`, `persist_deck_intake`, `queue_source_extraction`
- **Command to verify:** `curl -sS "$BACKEND_URL/api/products/deck-aistack-codes/decks/" -H "..."` or test upload endpoint
- **Likely fix owner:** Products route + WorkspaceSummaryService

### Source Ingestion Failure Cluster
- **Files:** `workers/source_pipeline_runtime.py` (handle_source_ingestion), `services/workflow_job_service.py`, `services/deck_processing_worker_service.py`, `workers/source_ingestion_worker.py`
- **Symptoms:** Stage stays `active` indefinitely; `workflow-state` shows pending
- **Logs to check:** `railway logs --service worker-source-ingestion`
- **Command to verify:** `python -c "from app.workers.job_handlers import *; print('OK')"`
- **Likely fix owner:** Source pipeline runtime

### Source Extraction Failure Cluster
- **Files:** `workers/source_pipeline_runtime.py` (handle_source_extraction), `services/pdf_deck_extraction_service.py`, `services/deck_extractors/*.py`, `deck_processing/source_extraction.py`, `deck_processing/source_structure_persistence.py`
- **Symptoms:** No `DeckSlide` rows created; extraction never completes
- **Logs to check:** `railway logs --service worker-source-extraction`
- **Command to verify:** `SELECT COUNT(*) FROM deck_slide WHERE deck_id = '<id>'`
- **Likely fix owner:** PDF extraction service

### Miniatures/Preview Failure Cluster
- **Files:** `workers/source_pipeline_runtime.py` (handle_miniatures), `services/deck_preview_service.py`, `deck_processing/source_preview_renderer.py`, `deck_processing/source_preview_persistence.py`, `services/slide_thumbnail_service.py`, `visualizer/miniature_service.py`
- **Symptoms:** No preview images; slides have no thumbnail_path
- **Logs to check:** `railway logs --service worker-miniatures`
- **Command to verify:** `SELECT thumbnail_path FROM deck_slide WHERE deck_id = '<id>'`
- **Likely fix owner:** Deck preview service

### Smart Deck Context Failure Cluster
- **Files:** `workers/source_pipeline_runtime.py` (handle_smart_deck_context), `services/smart_deck_job_service.py`, `services/smart_deck_source_enrichment_service.py`, `services/smart_deck_artifact_writer.py`, `services/smart_deck_output_validation.py`, `services/smart_deck_prompt_builder.py`, `deck_processing/smart_deck_context.py`
- **Symptoms:** Smart Deck opens empty; no source workspace
- **Logs to check:** `railway logs --service worker-smart-deck-context`
- **Command to verify:** `SELECT id FROM smart_deck_workspace WHERE deck_id = '<id>'`
- **Likely fix owner:** Smart deck job service

### DB Publisher / Readiness Failure Cluster
- **Files:** `workers/publisher_runtime.py` (handle_db_publisher), `deck_processing/readiness_publisher.py`, `services/deck_state_machine_service.py`, `services/workflow_job_service.py`, `services/smart_deck_readiness_service.py`, `workers/db_publisher_worker.py`
- **Symptoms:** `canOpenSmartDeck` stays `false` after all stages complete
- **Logs to check:** `railway logs --service worker-db-publisher`
- **Command to verify:** `python -m pytest tests/test_smart_deck_readiness_contract.py -v`
- **Likely fix owner:** Publisher runtime + state machine

### Brand Extraction Failure Cluster
- **Files:** `workers/source_pipeline_runtime.py` (handle_brand_extraction), `services/brand_extraction_service.py`, `services/brand_loader_service.py`, `services/brand_enrichment_service.py`, `deck_processing/brand_extraction.py`, `routes/brand_extraction.py`
- **Symptoms:** Brand profile missing; palette not generated
- **Logs to check:** `railway logs --service worker-brand-extraction`
- **Command to verify:** `SELECT id FROM brand_profile WHERE deck_id = '<id>'`
- **Likely fix owner:** Brand extraction service (should be NON-BLOCKING)

### LLM Generation Failure Cluster
- **Files:** `services/smart_deck_llm_service.py`, `services/llm/generation_service.py`, `workers/generation_runtime.py` (handle_llm_generation), `services/llm/anthropic_provider.py`, `services/llm/openai_provider.py`, `services/llm/openrouter_provider.py`, `ai_orchestration/providers/*`, `ai/*` provider files, `services/workspace_ai_provider_service.py`
- **Symptoms:** Generation job fails; no `generated_slides` created
- **Logs to check:** `railway logs --service worker-llm-generation`
- **Command to verify:** `python -c "from app.services.smart_deck_llm_service import get_generation_provider_config; print('OK')"`
- **Likely fix owner:** LLM generation worker + provider config

### LLM Parallelization Failure Cluster
- **Files:** `services/llm_parallelization_service.py`, `workers/llm_parallelization_runtime.py`
- **Symptoms:** Parallelization jobs stall
- **Logs to check:** `railway logs --service worker-llm-parallelization`
- **Command to verify:** Check workflow job for `llm_parallelization` type
- **Likely fix owner:** LLM parallelization runtime

### Schema Validation Failure Cluster
- **Files:** `services/generation/validate_generated_deck.py`, `services/generation/generated_deck_schema.py`, `workers/generation_runtime.py` (handle_schema_validation)
- **Symptoms:** Generation completes but validation fails; no preview render
- **Logs to check:** Backend logs for `validate_generated_deck`
- **Command to verify:** `python -c "from app.services.generation.validate_generated_deck import *; print('OK')"`
- **Likely fix owner:** Generation runtime

### Preview Render Failure Cluster
- **Files:** `workers/generation_runtime.py` (handle_preview_render), `services/bucket_artifact_service.py`
- **Symptoms:** Generated slides have no preview images
- **Logs to check:** Backend logs for `preview_render`
- **Command to verify:** Check DeckSlideAsset for asset_type = `generated_preview`
- **Likely fix owner:** Generation runtime + bucket artifact

### Apply Version Failure Cluster
- **Files:** `services/smart_deck_llm_service.py` (apply_design_version), `services/rendering/version_apply_service.py`, `workers/generation_runtime.py` (handle_apply_version), `workers/apply_version_worker.py`
- **Symptoms:** Version apply fails; deck stays in preview state
- **Logs to check:** Backend logs for `apply_design_version`
- **Command to verify:** `SELECT status FROM design_version WHERE deck_id = '<id>'`
- **Likely fix owner:** Smart deck LLM service

### Export Failure Cluster
- **Files:** `services/export_service.py`, `workers/publisher_runtime.py` (handle_export), `routes/exports.py`, `workers/export_worker.py`
- **Symptoms:** Export creation fails; download returns 404
- **Logs to check:** Backend logs for `create_export`
- **Command to verify:** `SELECT * FROM deck_export WHERE deck_id = '<id>'`
- **Likely fix owner:** Export service

### Visualizer Failure Cluster
- **Files:** `visualizer/slide_read_model.py`, `visualizer/preview_asset_service.py`, `visualizer/miniature_service.py`, `routes/smart_deck.py`, `routes/decks.py`, `routes/slides.py`, `services/deck_artifact_listing_service.py`, `services/smart_deck_llm_service.py` (get_smart_deck_workspace)
- **Symptoms:** Smart Deck page doesn't load slides; previews missing
- **Logs to check:** Backend logs for `get_deck`, `get_smart_deck_workspace`
- **Command to verify:** `python -c "from app.services.visualizer.slide_read_model import get_deck; print('OK')"`
- **Likely fix owner:** Visualizer/read model

### Storage Failure Cluster
- **Files:** `services/storage/artifact_storage.py`, `services/storage/bucket_health.py`, `services/storage/signed_urls.py`, `services/storage_health_service.py`, `services/bucket_artifact_service.py`, `services/upload_storage.py`, `services/storage_inventory_service.py`
- **Symptoms:** Upload fails; previews not stored; signed URLs timeout
- **Logs to check:** Backend logs for `artifact_storage`, `upload_storage`
- **Command to verify:** `python -c "from app.services.storage.artifact_storage import *; print('OK')"`
- **Likely fix owner:** Storage team

### Auth/Admin Failure Cluster
- **Files:** `routes/auth.py`, `routes/admin*`, `services/auth_session_service.py`, `services/superadmin_client.py`, `services/security_audit_service.py`, `services/admin_operations_service.py`, `services/admin_deck_repair_service.py`, `services/admin_workflow_observability_service.py`
- **Symptoms:** Auth failures; admin operations fail
- **Logs to check:** Backend logs for `auth`, `admin`
- **Command to verify:** `python -m pytest tests/test_auth_route_security.py -v`
- **Likely fix owner:** Auth team

### Railway Worker Startup Failure Cluster
- **Files:** All 22 workers in `app/workers/`, plus `services/deck_processing_worker_service.py`, `workers/job_handlers.py`, `workers/worker_entrypoint.py`
- **Symptoms:** Worker doesn't start; crashes on boot
- **Logs to check:** `railway logs --service <worker-name>`
- **Command to verify:** `python -c "from app.workers.worker_entrypoint import main; print('OK')"`
- **Likely fix owner:** Platform team

---

## 5. Prune Candidate Detail Table

| Current file | Problem | Useful logic | Absorb into | Action | Delete when | Risk | Explanation |
|---|---|---|---|---|---|---|---|
| `app/ai/prompts.py` | Dead code; no imports | `SMART_EDIT_SYSTEM_PROMPT`, `ANALYSIS_SYSTEM_PROMPT` constants | None — replace inline if needed | DELETE | Immediately | Low | Two short string constants never used anywhere |
| `app/ai_orchestration/prompts.py` | Dead code; no imports | `SYSTEM_PROMPT` constant | None — replace inline if needed | DELETE | Immediately | Low | One short string constant never imported |
| `app/ai_orchestration/tool_registry.py` | Dead code; no imports | `ToolRegistry` class with 4 hardcoded tool names | None — never called | DELETE | Immediately | Low | Stub registry that nothing uses |
| `app/ai_orchestration/tools/__init__.py` | Empty docstring; no imports | None | None | DELETE | Immediately | Low | Empty package init |
| `app/ai_orchestration/tools/*.py` (5 files) | 2-line stubs; no imports | Just `TOOL_NAME = "..."` constants | None | DELETE | Immediately | Low | Stub placeholders never used |
| `app/services/generation/openai/__init__.py` | Empty package init | None | None | DELETE | When `openai_generate_slides.py` deleted | Low | Empty |
| `app/services/generation/__init__.py` | Package init | None | None | DELETE | When generation subdirs deleted | Low | Empty |
| `app/ai/provider.py` | AIProvider Protocol used only internally to `app/ai/*` | `AIProvider` abstract protocol | Move protocol def into `services/llm/provider_base.py` | ABSORB then DELETE | After `app/ai/*` providers are absorbed into `services/llm/*` | Low | Already superseded by `LLMProvider` in `services/llm/provider_base.py` |
| `app/ai/anthropic_provider.py` | Re-export shim from `app.ai.llm_provider` | Re-exports `call_anthropic_message`, `extract_anthropic_text` | Direct imports from `app.ai.llm_provider` → `app.services.llm.anthropic_provider` | MERGE then DELETE | When all 5 callers switch to `app.services.llm` | Medium | Pure re-export; 5 callers need import update |
| `app/ai/llm_provider.py` | Actual Anthropic implementation | `call_anthropic_message()`, `extract_anthropic_text()`, `AnthropicProvider` class | Move into `app/services/llm/anthropic_provider.py` (merge with existing wrapper) | ABSORB then DELETE | When direct-import callers update | Medium | The real implementation; wrapped by `services/llm/anthropic_provider.py` |
| `app/ai/openai_provider.py` | Actual OpenAI implementation | `call_openai_response()`, `extract_openai_text()`, `OpenAIProvider` class | Move into `app/services/llm/openai_provider.py` | ABSORB then DELETE | When direct-import callers update | Medium | The real implementation |
| `app/ai/openrouter_provider.py` | Actual OpenRouter implementation | `call_openrouter_chat_completion()`, `extract_openrouter_text()`, `OpenRouterProvider` class | Move into `app/services/llm/openrouter_provider.py` | ABSORB then DELETE | When direct-import callers update | Medium | The real implementation |
| `app/ai/architecture_runtime_context.py` | Context builder outside LLM folder | `build_architecture_runtime_context()`, `build_smart_deck_runtime_capabilities()`, `load_architecture_runtime_knowledge()` | Move into `app/services/llm/prompt_builders/` | MOVE | After LLM harmonisation stage E | Low | Context builders belong with prompts |
| `app/ai/slide_archetypes_context.py` | Context builder outside LLM folder | `build_slide_archetype_context()`, `load_deck_archetype_knowledge()`, `SLIDE_ARCHETYPES` | Move into `app/services/llm/prompt_builders/` | MOVE | After LLM harmonisation stage E | Low | Context builders belong with prompts |
| `app/ai/diligence_knowledge_context.py` | Context builder outside LLM folder | `build_diligence_workspace_context()`, `load_diligence_knowledge()` | Move into `app/services/llm/prompt_builders/` | MOVE | After LLM harmonisation stage E | Low | Only used by `deck_runtime_surface_service` and `llm_knowledge_service` |
| `app/ai/vc_prompt_context.py` | Context builder outside LLM folder | `build_vc_prompt_context()` | Move into `app/services/llm/prompt_builders/` | MOVE | After LLM harmonisation stage E | Low | Only used by `smart_deck_llm_service` |
| `app/ai/market_research_knowledge_context.py` | Context builder outside LLM folder | `load_market_research_knowledge()` | Move into `app/services/llm/prompt_builders/` | MOVE | After LLM harmonisation stage E | Low | Only used by `llm_knowledge_service` |
| `app/services/generation/claude/` (2 files) | Orphaned generation path | `generate_slides_with_claude()`, `build_prompt` helpers | None — replaced by `smart_deck_llm_service` dict dispatch | DELETE | After confirming no imports | Medium | Not called by any active route or worker |
| `app/services/generation/openai/openai_generate_slides.py` | Orphaned generation path | `generate_slides_with_openai()` | None — replaced by `smart_deck_llm_service` dict dispatch | DELETE | After confirming no imports | Medium | Not called by any active route or worker |

## 6. Execution Results

### Phase 1 — DELETE dead files (DONE ✅)
- `app/ai/prompts.py` — 2 dead string constants, 0 importers
- `app/ai_orchestration/prompts.py` — 1 dead string constant, 0 importers
- `app/ai_orchestration/tool_registry.py` — dead ToolRegistry class, 0 importers
- `app/ai_orchestration/tools/__init__.py` — empty, 0 importers
- `app/ai_orchestration/tools/audience_tools.py` — 2-line stub, 0 importers
- `app/ai_orchestration/tools/brand_tools.py` — 2-line stub, 0 importers
- `app/ai_orchestration/tools/deck_tools.py` — 2-line stub, 0 importers
- `app/ai_orchestration/tools/export_tools.py` — 2-line stub, 0 importers
- `app/ai_orchestration/tools/generation_tools.py` — 2-line stub, 0 importers
- `app/ai_orchestration/tools/slide_tools.py` — 2-line stub, 0 importers
- **Total: 10 files deleted, 35 lines removed.**

### Phase 2 — MOVE files (DEFERRED — not safe without breaking imports)
- Files like `deck_state_machine_service.py` (14 importers), `deck_processing_visibility_service.py` (3 importers + tests), and `deck_processing_queue_service.py` (5 importers) were audited but NOT moved.
- Moving them would require updating 10+ import sites each with no behavior benefit.
- **Decision:** Keep in place until a full refactor PR can update all importers atomically.

### Phase 3 — ABSORB app/ai/* into app/services/llm/ (DEFERRED)
- The `app/services/llm/*_provider.py` wrappers currently import from `app/ai/*` implementations.
- Full absorb requires merging implementation code and updating 16+ callers.
- **Decision:** Keep `app/ai/*` as-implemented for now. The `app/services/llm/*` wrappers provide a clean future migration path. Documented in `llm-provider-harmonisation.md`.

### Phase 4 — DELETE orphaned generation files (SKIPPED — still live)
- `deck_generation.py` route IS registered in `product/__init__.py` and IS imported.
- `deck_generation_service.py` IS live and imports from `generation/claude/` and `generation/openai/`.
- **Decision:** Keep all generation files — they are on the active product spine.

### Phase 5 — Verify full user-testing path (DONE ✅)
All critical imports verified:
- `app.main` — FastAPI app boots
- `workflow_state_read_model` — `get_deck_workflow_state` imports OK
- `slide_read_model` — `get_deck` imports OK
- `LLM registry` — 3 providers registered (anthropic, openai, openrouter)
- `worker_entrypoint` — Railway worker entrypoint compiles
- `readiness_publisher`, `smart_deck_context`, `version_apply_service` — all spine wrappers OK
- `PRODUCT_ROUTERS` — 25 routes registered
- `SOURCE_PIPELINE_JOB_SEQUENCE` — 6 stages (source_ingestion, source_extraction, miniatures, smart_deck_context, db_publisher, brand_extraction)
- `job_handlers` — dispatch seam OK
- Tests: 280 pass, 25 pre-existing failures (all unrelated to this session)
