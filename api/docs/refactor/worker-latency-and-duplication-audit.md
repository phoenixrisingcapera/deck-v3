# Worker Latency & Duplication Audit

## Per-Stage Analysis

### Stage 1 — Source Ingestion

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES | If `claim_next_workflow_job` is called by multiple workers with overlapping `DECK_WORKER_JOB_TYPES`, two workers can claim the same job type. Mitigation: the workflow job system uses `SELECT ... FOR UPDATE SKIP LOCKED`-style atomic claiming — only one worker gets the row. |
| Duplicate rendering | N/A | No rendering in this stage. |
| Duplicate LLM calls | N/A | No LLM calls in this stage. |
| Duplicate DB writes | LOW | Worker writes output_payload to `WorkflowJob.output_json`. Only one worker claims the job, so only one write occurs. |
| Worker imports heavy | LOW | Imports `sqlalchemy`, `app.db.models`, `app.workers.dispatch.worker_runtime_service`, `app.services.deck_processing.workflow_jobs`. No heavy ML/AI dependencies. |
| Startup imports reducible | NO | Imports are minimal — DB models and workflow job helpers are required. |
| Loads unnecessary providers | NO | No provider imports. |
| Latency cleanup | None needed. Payload is purely a confirmation stage (file already persisted by upload route). | |

### Stage 2 — Source Extraction

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES (same mitigation) | Atomic claiming prevents double execution. |
| Duplicate rendering | N/A | No rendering. |
| Duplicate LLM calls | N/A | No LLM calls. |
| Duplicate DB writes | MEDIUM | `extract_and_persist_deck_structure` writes `DeckSlide`, `DeckSlideBlock`, `DeckSlideAsset`. Re-running on same deck could duplicate rows if idempotency keys are absent. Mitigation: extraction run ID scopes the write. |
| Worker imports heavy | LOW | Same as stage 1 + `app.services.deck_processing.source_structure_persistence`. |
| Startup imports reducible | NO | PDF extraction libraries loaded lazily by the service. |
| Loads unnecessary providers | NO | No provider imports. |
| Latency cleanup | None needed. The heavy work (PDF parsing) is in the service, not the worker. | |

### Stage 3 — Miniatures

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES (same mitigation) | Atomic claiming prevents double execution. |
| Duplicate rendering | MEDIUM | `extract_source_previews` generates preview images. If re-run, it overwrites existing `DeckSlideAsset` rows with `asset_type='source_preview'`. No duplicate files accumulate but re-rendering is wasteful. Mitigation: only claim once. |
| Duplicate LLM calls | N/A | No LLM calls. |
| Duplicate DB writes | MEDIUM | Preview persistence uses upsert or replace. Overwrites are safe but waste I/O. |
| Worker imports heavy | LOW | `app.services.visualizer.miniature_service` loads PyMuPDF transitively. |
| Startup imports reducible | NO | All imports needed at runtime. |
| Loads unnecessary providers | NO | No provider imports. |
| Latency cleanup | Consider adding a `preview_generated_at` gate in the worker to skip if thumbnails already exist. | |

### Stage 4 — Smart Deck Context

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES (same mitigation) | Atomic claiming prevents double execution. |
| Duplicate rendering | N/A | No rendering. |
| Duplicate LLM calls | MEDIUM | `prepare_smart_deck_source_workspace` can trigger LLM enrichment if configured. Re-running would repeat enrichment calls. Mitigation: enrichment is optional and gated by the service. |
| Duplicate DB writes | MEDIUM | Workspace creation is idempotent (checks existence before creating). |
| Worker imports heavy | LOW | Same baseline. |
| Startup imports reducible | NO | All needed. |
| Loads unnecessary providers | NO | Provider calls are gated by service, not worker. |
| Latency cleanup | Consider checking workspace already exists before calling prepare. | |

### Stage 5 — DB Publisher

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES | Atomic claiming. |
| Duplicate rendering | N/A | No rendering. |
| Duplicate LLM calls | N/A | No LLM calls. |
| Duplicate DB writes | MEDIUM | `transition_deck_state` with `DeckState.READY` is idempotent — re-applying READY is a no-op after the first. |
| Worker imports heavy | LOW | Imports `app.services.deck_processing.state_machine`. |
| Startup imports reducible | NO | Lightweight imports. |
| Loads unnecessary providers | NO | No providers. |
| Latency cleanup | None needed. Pure state transition. | |

### Stage 6 — Brand Extraction

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES | Atomic claiming. |
| Duplicate rendering | N/A | No rendering. |
| Duplicate LLM calls | MEDIUM | `run_brand_extraction_for_deck` may call LLM for enrichment if website URL present. Re-running repeats the call. |
| Duplicate DB writes | LOW | Brand profile upsert is idempotent. |
| Worker imports heavy | LOW | `app.services.brand.company_profile`, `app.services.deck_processing.brand_extraction`. |
| Startup imports reducible | NO | Lightweight. |
| Loads unnecessary providers | NO | Provider calls gated by service. |
| Latency cleanup | Consider gating brand extraction on `not deck.brand_profile` or `brand_profile.processing_status != 'completed'`. | |

### Stage 7 — LLM Generation

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES | Atomic claiming. |
| Duplicate rendering | N/A | No rendering. |
| Duplicate LLM calls | HIGH | `create_generation_job` in `app.services.llm.generation_service` calls the LLM provider. Re-running on the same deck would create a NEW generation job + ANOTHER LLM call. **This is the highest-latency risk in the worker layer.** |
| Duplicate DB writes | MEDIUM | Generation job creation is not idempotent — each call creates a new `GenerationJob` row. |
| Worker imports heavy | MEDIUM | `app.services.llm.generation_service` transitively imports provider SDKs (Anthropic, OpenAI, OpenRouter). |
| Startup imports reducible | PARTIALLY | `from app.schemas.smart_deck import CreateSmartDeckGenerationJobInput` is a Pydantic schema import — negligible weight. The heavy provider imports are in the service, loaded lazily at handler call time (not worker startup). |
| Loads unnecessary providers | YES — in theory | All three provider SDKs (Anthropic, OpenAI, OpenRouter) are imported transitively via `generation_service`. Only one is used per call. Mitigation: provider SDKs are loaded at module level, but most of the weight is in service imports, not the worker handler itself. |
| Latency cleanup | HIGH PRIORITY. If two workers can claim `llm_generation` jobs for the same deck, duplicate LLM calls and generation jobs occur. The claiming layer (`claim_next_workflow_job`) should prevent this by locking the job row. Verify that `claim_next_workflow_job` uses atomic `FOR UPDATE SKIP LOCKED` with a unique job constraint. | |

### Stage 8 — LLM Parallelization

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES | Atomic claiming. |
| Duplicate rendering | N/A | No rendering. |
| Duplicate LLM calls | HIGH | `summarize_parallelization_result` calls LLM for each partition. Re-running repeats ALL partition calls. |
| Duplicate DB writes | MEDIUM | Artifact writes overwrite storage key. |
| Worker imports heavy | HIGH | `pyspark` is a ~200MB dependency. Only loaded in `Dockerfile.pyspark`. |
| Startup imports reducible | NO | PySpark is unavoidable for this stage. |
| Loads unnecessary providers | NO | Only LLM providers needed for the configured model. |
| Latency cleanup | The Spark session is created fresh per job (`_spark_session`). Consider reusing a singleton SparkSession across jobs within the same worker process. SparkSession creation incurs JVM startup overhead (~5-15s). | |

### Stage 9 — Schema Validation

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES | Atomic claiming. |
| Duplicate rendering | N/A | No rendering. |
| Duplicate LLM calls | N/A | No LLM calls. |
| Duplicate DB writes | LOW | Only writes job status. Idempotent. |
| Worker imports heavy | LOW | `app.services.rendering.schema_validation` loads schema JSON files. Lightweight. |
| Startup imports reducible | NO | Minimal weight. |
| Loads unnecessary providers | NO | No providers. |
| Latency cleanup | None needed. Quick DB read + schema check. | |

### Stage 10 — Preview Render

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES | Atomic claiming. |
| Duplicate rendering | MEDIUM | The render itself (generating preview images) is performed by a downstream service. The worker only records a manifest artifact. Re-running overwrites the artifact. |
| Duplicate LLM calls | N/A | No LLM calls. |
| Duplicate DB writes | LOW | Artifact record is upserted. |
| Worker imports heavy | LOW | Light imports. |
| Startup imports reducible | NO | Minimal. |
| Loads unnecessary providers | NO | No providers. |
| Latency cleanup | None needed. Pure artifact recording. | |

### Stage 11 — Apply Version

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES | Atomic claiming. |
| Duplicate rendering | N/A | No rendering. |
| Duplicate LLM calls | N/A | No LLM calls in the worker. `apply_design_version` updates DB state only. |
| Duplicate DB writes | MEDIUM | Version apply is idempotent (state transition). |
| Worker imports heavy | LOW | `from app.services.llm.generation_service import apply_design_version`. Only pulls the apply function, not full generation imports. |
| Startup imports reducible | NO | Light. |
| Loads unnecessary providers | NO | Not in this call path. |
| Latency cleanup | None needed. | |

### Stage 12 — Export

| Concern | Status | Details |
|---|---|---|
| Duplicate jobs can run | YES | Atomic claiming. |
| Duplicate rendering | N/A | No rendering. |
| Duplicate LLM calls | N/A | No LLM calls. |
| Duplicate DB writes | MEDIUM | Export creation (`create_export`) writes to `DeckExport`. Duplicate jobs could create duplicate export rows. Mitigation: worker should reject if export already exists for this job. |
| Worker imports heavy | LOW | `from app.services.rendering.export_service import create_export`. Light. |
| Startup imports reducible | NO | Minimal. |
| Loads unnecessary providers | NO | No providers. |
| Latency cleanup | Consider checking `DeckExport` for existing exports of the same type before creating. | |

## Cross-Cutting Concerns

### Worker startup import weight

| File | Import weight | Notes |
|---|---|---|
| `entrypoints/deck_queue_worker.py` | LOW | Imports `worker_runtime_service`, `worker_health`, `render_schema_service`. No ML/providers. |
| `dispatch/worker_runtime_service.py` | LOW | DB models + workflow job helpers. |
| `dispatch/job_handlers.py` | NEGLIGIBLE | String constants only. Actual runtime modules loaded lazily inside `get_workflow_job_handler()`. |
| `runtime/source_pipeline_runtime.py` | LOW | Service imports are at module level but services are lightweight (no provider SDKs). |
| `runtime/generation_runtime.py` | MEDIUM | `app.services.llm.generation_service` transitively loads provider SDKs. However, the worker only imports the function reference; provider SDKs are loaded when `generation_service` is imported. |
| `runtime/publisher_runtime.py` | LOW | Lightweight. |
| `runtime/llm_parallelization_runtime.py` | HIGH | `pyspark` (~200MB). However, only present in `Dockerfile.pyspark` image, not in regular worker images. |

### Unnecessary provider loading

The only worker file that loads unnecessary providers is `generation_runtime.py` via `app.services.llm.generation_service`. This service is the orchestration hub for all LLM providers (Anthropic, OpenAI, OpenRouter). While the monolithic import is not ideal, it's the existing architecture and the service consolidation is tracked in the LLM harmonisation plan (`docs/refactor/llm-provider-harmonisation.md`).

**Current load:** All 3 provider SDKs imported at process startup if the `generation_runtime` module is imported.
**Mitigation:** Future LLM provider split would make each provider a lazy-loaded plugin.

### Inefficient DB polling

`deck_queue_worker.py` polls `claim_next_workflow_job` every `POLL_INTERVAL_SECONDS` (default 10s). This is a busy-poll loop that runs even when no jobs are available.

**Impact:** Low — one SELECT query per 10s is negligible DB load.
**Mitigation:** Could use `LISTEN/NOTIFY` or a sleep-with-backoff, but not worth the complexity for the current scale.

### Duplicated artifact writes

`record_workflow_artifact` is called in `publisher_runtime.py::handle_export` and `generation_runtime.py::handle_preview_render`. Each call creates a `WorkflowJobArtifact` row. If a job is re-processed (e.g., after recovery), duplicate artifact rows could accumulate.

**Mitigation:** Add `artifact_type + job_id` unique constraint, or check existence before writing.

## Priority Ranking

| Rank | Issue | Stage | Impact |
|---|---|---|---|
| 1 | Duplicate LLM calls on re-claim | 7 (LLM Generation) | HIGH — real API cost + latency |
| 2 | SparkSession created per job (15s overhead) | 8 (LLM Parallelization) | HIGH — adds 15s to every parallelization job |
| 3 | Duplicate generation job rows | 7 (LLM Generation) | MEDIUM — wasted DB rows |
| 4 | Duplicate export rows | 12 (Export) | MEDIUM — wasted DB rows |
| 5 | Duplicate artifact rows | 10, 12 | LOW — minor DB bloat |
| 6 | Busy-poll every 10s | all (polling loop) | LOW — negligible DB load |
| 7 | All providers loaded at startup | 7 (generation_runtime) | LOW — provider SDKs not heavy enough to matter |

## Recommendations

1. **Validate `claim_next_workflow_job` atomicity** — ensure it uses `SELECT ... FOR UPDATE SKIP LOCKED` so no two workers claim the same job.
2. **Add idempotency checks** in high-impact handlers (LLM generation, export) to skip if work is already done.
3. **Reuse SparkSession** across jobs in the `llm_parallelization` worker process instead of creating per-job.
4. **Skip miniatures if thumbnails exist** — add a `preview_generated_at` gate.
5. **Skip brand extraction if already completed** — check `brand_profile.processing_status`.
6. **Add unique constraint on `WorkflowJobArtifact(job_id, artifact_type)`** to prevent duplicate artifact rows.
7. **Future: lazy-load provider SDKs** in `generation_service` so only the configured provider is loaded.
