# Backend Ownership Audit: Upload to Smart Deck

Date: 2026-07-03

Branch: `backend-ownership-audit-docs`

Scope: audit and proposed structure only. This document does not authorize deletion and does not change runtime behavior.

## Product Path To Preserve

```text
Upload deck
-> queue source processing
-> source ingestion
-> source extraction
-> miniatures / previews
-> Smart Deck context preparation
-> db_publisher marks Smart Deck ready
-> workflow-state returns canOpenSmartDeck=true
-> frontend visualizer opens the deck
```

The visualizer is product-critical. Do not prune any file that creates, stores, reads, or serves slide previews, miniatures, `DeckSlide` records, `DeckSlideAsset` records, or workflow-state until the replacement owner is proven.

## Ownership Rule

There should be one owner per responsibility:

- Only source extraction extracts and persists source deck structure.
- Only miniatures/previews render visual source assets.
- Only Smart Deck context prepares the Smart Deck source workspace.
- Only `db_publisher` marks Smart Deck ready.
- Only workflow-state tells the frontend when Smart Deck can open.
- LLM functions should live under a clear LLM service area.
- Visualizer, preview, and read-model functions should live under a clear visualizer service area.
- Extraction functions should live under a clear source-processing area.

## Canonical Upload To Smart Deck Path

| Step | Current owner | Entry point / file | Notes |
| --- | --- | --- | --- |
| Upload deck | Product upload routes and workspace upload service | `app/api/routes/products.py`, `app/services/workspace_summary_service.py`, `app/services/upload_storage.py` | Upload saves source file and returns manual Smart Deck start metadata. |
| Queue source processing | Workflow service | `app/services/deck_workflow_service.py::queue_source_extraction` | Creates or requeues the durable source pipeline. |
| Source ingestion | Source pipeline runtime | `app/workers/source_pipeline_runtime.py::handle_source_ingestion` | Confirms source file metadata and marks `source_file_saved`. |
| Source extraction | Source pipeline runtime plus structure service | `handle_source_extraction`, `app/services/deck_structure_service.py`, `app/services/pdf_deck_extraction_service.py` | Extracts text/structure and persists `DeckSlide`, `DeckSlideBlock`, and embedded `DeckSlideAsset` rows. Source extraction should not render canonical previews or prepare Smart Deck workspace. |
| Miniatures / previews | Miniatures stage plus preview service | `handle_miniatures`, `app/services/deck_preview_service.py` | Renders source previews against existing source slides and persists canonical `source_preview` assets. |
| Smart Deck context | Smart Deck context stage | `handle_smart_deck_context`, `app/services/smart_deck_job_service.py` | Builds Smart Deck source workspace, source versions, source run, and source artifacts from persisted extracted slides. |
| Publish readiness | Publisher runtime | `app/workers/publisher_runtime.py::handle_db_publisher` | Only this stage should transition deck state to `ready` for `smart_deck_ready`. |
| Workflow-state read model | Workflow service | `app/api/routes/deck_workflow.py`, `app/services/deck_workflow_service.py::get_deck_workflow_state` | Returns `canOpenSmartDeck`, phase, stages, source counts, preview counts, failures, provider state, and links. |
| Visualizer/read model | Deck service and Smart Deck route | `app/services/deck_service.py`, `app/api/routes/smart_deck.py`, `app/services/smart_deck_llm_service.py::get_smart_deck_workspace` | Serves slide, preview, workspace, generated slide, and render schema data consumed by the frontend visualizer. |

## Current Durable Job Sequence

`app/services/workflow_job_service.py` currently defines the source pipeline as:

```text
source_ingestion
-> source_extraction
-> miniatures
-> smart_deck_context
-> db_publisher
-> brand_extraction
```

This sequence puts `brand_extraction` after publisher dependency selection, so brand is not in the critical path for Smart Deck readiness. Keep that property for MVP unless product logic explicitly changes.

## Worker Audit

| Worker file | Job type handled | Required for MVP Upload -> Smart Deck | Duplicate ownership | Recommendation | Risk |
| --- | --- | --- | --- | --- | --- |
| `app/workers/deck_queue_worker.py` | Generic worker process shell | Yes, if used by Railway as worker entrypoint | Overlaps with per-kind wrapper files only as process startup | Keep | High |
| `app/workers/job_handlers.py` | Dispatches job type to runtime handler | Yes | None. Keep it dumb. | Keep | Low |
| `app/workers/source_pipeline_runtime.py` | `source_ingestion`, `source_extraction`, `miniatures`, `brand_extraction`, `smart_deck_context` | Yes | Contains multiple stage handlers in one file; acceptable for now but should split later | Split later by stage after behavior is stable | High |
| `app/workers/source_ingestion_worker.py` | `source_ingestion` wrapper | Yes if Railway has per-stage service | Wrapper around generic worker config | Keep until Railway service mapping is proven | Medium |
| `app/workers/source_extraction_worker.py` | `source_extraction` wrapper | Yes | Wrapper around generic worker config | Keep until Railway service mapping is proven | Medium |
| `app/workers/miniatures_worker.py` | `miniatures` wrapper | Yes | Wrapper around generic worker config | Keep until Railway service mapping is proven | Medium |
| `app/workers/smart_deck_context_worker.py` | `smart_deck_context` wrapper | Yes | Wrapper around generic worker config | Keep until Railway service mapping is proven | Medium |
| `app/workers/db_publisher_worker.py` | `db_publisher` wrapper | Yes | Wrapper around generic worker config | Keep. This is readiness-critical. | High |
| `app/workers/brand_extraction_worker.py` | `brand_extraction` wrapper | Not critical for MVP readiness | Brand runtime shares source pipeline file | Keep, but keep optional for readiness | Medium |
| `app/workers/generation_runtime.py` | `llm_generation`, `schema_validation`, `preview_render`, `apply_version`, `compile_final_deck` | Not required to open source Smart Deck, required for generation/apply flows | Multiple generation-side responsibilities in one runtime | Split later under LLM/visualizer/apply ownership | High |
| `app/workers/llm_generation_worker.py` | `llm_generation` wrapper | Post-open generation flow | Wrapper | Keep until Railway mapping is proven | Medium |
| `app/workers/llm_parallelization_runtime.py` | `llm_parallelization` runtime | Not MVP open path | Separate runtime already | Keep, out of source path | Medium |
| `app/workers/schema_validation_worker.py` | `schema_validation` wrapper | Post-generation | Wrapper | Keep until generation flow audited | Medium |
| `app/workers/preview_render_worker.py` | `preview_render` wrapper | Post-generation visualizer preview, not source miniatures | Naming can confuse with source preview service | Keep but rename/split later only after frontend verification | Medium |
| `app/workers/apply_version_worker.py` | `apply_version` wrapper | Post-generation apply | Wrapper | Keep | Medium |
| `app/workers/compile_final_deck_worker.py` | `compile_final_deck` wrapper | Export/final deck path | Wrapper | Keep until export/final path audited | Medium |
| `app/workers/export_worker.py` | `export` wrapper | Export path | Wrapper | Keep | Medium |
| `app/workers/publisher_runtime.py` | `db_publisher`, `export` | `db_publisher` required | Export handling shares publisher runtime; readiness publish is cleanly centralized | Keep, consider export split later | High |
| `app/workers/stale_job_rescuer_worker.py` | Recovery only | Operationally required | None | Keep | High |

## Service Ownership Audit

| File path | Current responsibility | Should own | Must not own | Duplicate ownership found | Proposed target folder | Recommended action |
| --- | --- | --- | --- | --- | --- | --- |
| `app/services/workflow_job_service.py` | Job type constants, sequence, dependencies, idempotency, status transitions | Workflow contract and durable job primitives | Runtime business logic or frontend read model | Phase names overlap with read model by necessity | `services/deck_processing/workflow_jobs.py` or `workers/job_contract.py` | Keep |
| `app/services/deck_workflow_service.py` | Queueing workflow jobs and building workflow-state | Queue commands and canonical workflow-state read model | Worker execution, extraction, preview rendering, workspace writes, direct READY publication | Currently contains both command queueing and read-model projection | `services/deck_processing/workflow_state_read_model.py` plus command module | Split later |
| `app/services/deck_processing_worker_service.py` | Worker kind, claiming, heartbeat, recovery, dispatch shell | Generic worker runtime infrastructure | Stage business logic | Some failure propagation is source-pipeline specific | `workers/job_runtime.py` | Keep, split source-specific helpers later |
| `app/services/deck_structure_service.py` | Clears and persists source structure; returns source views | Source structure persistence and readback | PDF parsing, previews, Smart Deck workspace, readiness publishing | Overloaded destructive cleanup covers generated workspace and downstream state | `services/deck_processing/source_structure_persistence.py` | Split later, high risk |
| `app/services/pdf_deck_extraction_service.py` | Deterministic PDF structure extraction | In-memory parsing only | DB writes, readiness, Smart Deck workspace, canonical previews | Optional thumbnail rendering delegates to `slide_thumbnail_service.py` | `services/deck_processing/source_extraction.py` | Keep, keep `include_thumbnails=False` in source path |
| `app/services/slide_thumbnail_service.py` | Low-level PDF page thumbnail helper | Renderer helper only | Product preview ownership | Conceptually overlaps with source previews | `services/visualizer/preview_asset_service.py` or renderer helper | Keep until unified preview strategy exists |
| `app/services/deck_preview_service.py` | Renders source previews and persists `source_preview` assets | Canonical miniatures/source preview stage | Source slide creation, extraction, Smart Deck workspace, readiness by default | Has optional `publish_ready_state`; keep false in workflow | `services/deck_processing/source_preview_persistence.py` plus renderer | Keep, remove readiness option in Phase 1 if unused |
| `app/services/presentation_miniature_service.py` | Legacy naming shim delegating to preview service | Nothing long-term except compatibility | Preview ownership | Duplicates `deck_preview_service.py` | `legacy/` or prune later | Prune later after call-site proof |
| `app/services/smart_deck_job_service.py` | Smart Deck source workspace preparation | Source workspace/context writer | Extraction, preview rendering, final readiness | None acceptable; protect this as single writer | `services/deck_processing/smart_deck_context.py` | Keep |
| `app/services/smart_deck_llm_service.py` | Workspace read model, preferences, messages, generation helpers, LLM generation | Split into Smart Deck read model, preferences, generation orchestration, provider calls | Source extraction or readiness | Large mixed surface: visualizer read model plus LLM generation | `services/visualizer/slide_read_model.py`, `services/llm/generation_service.py` | Split later |
| `app/services/smart_deck_artifact_writer.py` | Writes Smart Deck artifacts | Artifact persistence for Smart Deck source/generation | Readiness | Clear owner | `services/llm/artifact_service.py` or `deck_processing/artifact_service.py` | Keep |
| `app/services/smart_deck_source_enrichment_service.py` | Optional LLM source label enrichment | Source-context enrichment | Raw extraction or readiness | Touches LLM provider from source-context path | `services/llm/source_enrichment_service.py` | Keep optional, do not block readiness |
| `app/services/smart_deck_prompt_builder.py` | Builds source context and enrichment prompts | Prompt/context shaping | Persistence or readiness | None | `services/llm/prompt_builder.py` | Keep |
| `app/services/deck_service.py` | Deck graph/read model and preview URLs | Visualizer/deck read model | Workflow mutation | Reads `DeckSlideAsset` source previews | `services/visualizer/slide_read_model.py` | Split later |
| `app/services/workspace_dashboard_service.py` | Dashboard deck summary and thumbnail URLs | Dashboard read model | Readiness ownership | Reads workflow-state and previews | `services/visualizer/slide_read_model.py` or dashboard | Keep |
| `app/services/deck_processing_visibility_service.py` | Product processing visibility wrapper | UI-friendly processing projection | Canonical readiness source | Duplicates parts of workflow-state | Fold toward workflow-state later | Split/prune later after frontend verification |
| `app/services/smart_deck_readiness_service.py` | Readiness diagnostics | Admin/readiness diagnostics | Readiness mutation | Duplicates workflow-state readiness logic | `services/admin/diagnostics.py` | Keep as diagnostic only |
| `app/services/brand_extraction_service.py` | Brand extraction and brand profile signals | Brand profile generation | Smart Deck readiness for MVP | Reads source previews/assets | `services/brand/` or `services/deck_processing/brand_extraction.py` | Keep optional |
| `app/services/upload_service.py` | Legacy upload and state transitions | Legacy upload support | Canonical product upload path if unused | Can queue/transition outside product path | Legacy unknown | Do not delete yet |
| `app/services/workspace_summary_service.py` | Product workspace upload/session/decks | Product upload entry support | Worker execution | Canonical product upload support | `services/deck_processing/deck_upload.py` | Keep |
| `app/services/upload_storage.py` | Upload file storage | Storage | Processing/readiness | None | `services/storage/artifact_storage.py` | Keep |
| `app/services/bucket_artifact_service.py` | Bucket artifact storage/signing | Artifact storage | Product workflow decisions | None | `services/storage/artifact_storage.py` | Keep |
| `app/services/storage_health_service.py` | Storage health | Health diagnostics | Runtime workflow | None | `services/storage/bucket_health.py` | Keep |
| `app/services/export_service.py` | Export creation/download | Export | Smart Deck readiness | Export ready shares publisher runtime | `services/export/` or `services/visualizer/export_service.py` | Keep |

## Route Audit

| Route file | Endpoint family | Frontend likely uses it | Queues processing | Class | Prune later? |
| --- | --- | --- | --- | --- | --- |
| `app/api/routes/products.py` | `/api/products/deck-aistack-codes/*` product upload/workspace/deck actions | Yes | Yes, `/decks/{deck_id}/smart-deck/start`, `/retry` | Canonical product plus some compatibility | Do not prune |
| `app/api/routes/deck_workflow.py` | Product workflow-state and workflow commands | Yes | Yes | Canonical workflow contract | Do not prune |
| `app/api/routes/smart_deck.py` | Smart Deck workspace, generation, preferences, generated slide code | Yes | Yes for generation/apply wrappers | Canonical Smart Deck | Do not prune |
| `app/api/routes/decks.py` | Global `/api/decks` deck graph, legacy deck actions, export | Yes | Some legacy queue paths | Mixed canonical/legacy | Prune only after frontend route audit |
| `app/api/routes/product_upload_compat.py` | Upload compatibility | Likely yes for old frontend paths | Possibly | Compatibility | Prune later only after frontend proof |
| `app/api/routes/deck_retry_rescue.py` | Retry rescue | Admin/product recovery | Yes | Rescue | Keep until failure recovery replaced |
| `app/api/routes/upload_rescue.py` | Upload rescue/status | Recovery | Yes | Rescue | Keep until production incidents stop depending on it |
| `app/api/routes/deck_artifacts.py` | Artifact listing | Frontend/admin likely | No | Visualizer/artifacts | Do not prune until visualizer verified |
| `app/api/routes/slides.py` | Slide preview/assets | Yes | No | Visualizer critical | Do not prune |
| `app/api/routes/shell.py` | Deck shell workspace/properties | Yes | Some compile paths | Canonical/legacy shell | Keep |
| `app/api/routes/exports.py` | Export endpoints | Yes | Yes | Canonical export | Keep |
| `app/api/routes/brand_extraction.py` | Brand extraction | Maybe | Yes/async | Optional product stage | Keep optional |
| `app/api/routes/product_runtime_hardening.py` | Runtime hardening helpers | Unknown/admin/product | No | Safety/repair | Legacy unknown, do not delete yet |
| `app/api/routes/admin_operations.py` | Admin operations | Admin | Some repair/retry | Admin | Keep |
| `app/api/routes/deployment_readiness.py` | Deployment readiness | Admin/ops | No | Admin health | Keep |
| `app/api/routes/health.py` | Health | Yes/ops | No | Admin health | Keep |
| `app/api/routes/assistant.py` | Assistant runs | Yes | Some LLM | Product LLM | Keep |
| `app/api/routes/smart_edit.py` | Smart Edit | Yes | LLM/edit | Product LLM/edit | Keep, outside MVP path |
| `app/api/routes/analysis.py` | Analysis | Maybe | LLM/analysis | Product analysis | Keep until frontend audit |
| `app/api/routes/blocks.py` | Blocks | Maybe | No | Edit/read model | Keep until frontend audit |
| `app/api/routes/deck_generation.py` | Deck generation | Maybe legacy | Yes | Legacy/generation | Legacy unknown |
| `app/api/routes/deck_intake.py` | Intake/change preview/source extraction | Maybe | Yes | Compatibility/intake | Legacy unknown |
| `app/api/routes/workspace_dashboard.py` | Dashboard | Yes | No | Read model | Keep |
| `app/api/routes/workspace_ai_provider.py` | Provider settings | Yes | No | LLM/provider | Keep |
| `app/api/routes/llm_knowledge_admin.py` | LLM knowledge admin | Admin | No | Admin/LLM | Keep |
| `app/api/routes/failure_tickets.py` | Failure tickets | Admin/frontend reports | No | Admin diagnostics | Keep |

## Proposed Folder Structure

```text
app/
  api/
    routes/
      deck_upload.py
      deck_workflow.py
      smart_deck.py
      admin_health.py

  services/
    deck_processing/
      source_pipeline.py
      source_ingestion.py
      source_extraction.py
      source_structure_persistence.py
      source_preview_renderer.py
      source_preview_persistence.py
      smart_deck_context.py
      readiness_publisher.py
      workflow_state_read_model.py

    llm/
      provider_client.py
      prompt_builder.py
      generation_service.py
      critique_service.py
      repair_service.py
      artifact_service.py

    visualizer/
      slide_read_model.py
      miniature_service.py
      preview_asset_service.py
      render_schema_service.py

    storage/
      artifact_storage.py
      signed_urls.py
      bucket_health.py

    admin/
      diagnostics.py
      worker_health.py
      llm_knowledge_health.py

  workers/
    source_worker.py
    generation_worker.py
    export_worker.py
    stale_job_rescuer.py
    job_handlers.py
```

## Safe Refactor Plan

### PR 1: Stop Duplicate Readiness And Preview Side Effects

- Make `db_publisher` the only source pipeline stage allowed to publish Smart Deck readiness.
- Remove or disable READY transitions from rendering/extraction services.
- Keep workflow-state as the only frontend readiness contract.
- Make `miniatures` the only active source preview rendering stage.
- Keep brand extraction optional for Smart Deck readiness.

### PR 2: Create Target Folders And Move Internals Without Behavior Change

- Add `services/deck_processing`, `services/llm`, `services/visualizer`, `services/storage`, and `services/admin`.
- Move modules with import-only changes.
- Do not rename public API routes.

### PR 3: Split Overloaded Services

- Split `deck_structure_service.py` into extraction persistence and readback modules.
- Split `deck_workflow_service.py` into command queueing and workflow-state read model.
- Split `smart_deck_llm_service.py` into visualizer read model, preferences/messages, and generation services.

### PR 4: Prune Duplicate Workers And Wrappers

- Apply the worker pruning rule before deleting any worker.
- Delete only wrappers proven unused by Railway and routes.

### PR 5: Prune Dead Routes After Frontend Verification

- Compare frontend API proxy paths against backend route families.
- Remove only routes with no frontend/admin/Railway usage and no rescue dependency.

### PR 6: Visualizer Hardening

- Verify source previews, `DeckSlide`, `DeckSlideAsset`, workflow-state, and Smart Deck workspace payloads.
- Harden fallback/degraded visualizer behavior before deleting any preview/read-model code.

## Do Not Delete Yet

Do not delete these until replacement ownership and live usage are proven:

- `app/services/workflow_job_service.py`
- `app/services/deck_workflow_service.py`
- `app/services/deck_processing_worker_service.py`
- `app/workers/job_handlers.py`
- `app/workers/source_pipeline_runtime.py`
- `app/workers/publisher_runtime.py`
- `app/workers/deck_queue_worker.py`
- `app/workers/source_ingestion_worker.py`
- `app/workers/source_extraction_worker.py`
- `app/workers/miniatures_worker.py`
- `app/workers/smart_deck_context_worker.py`
- `app/workers/db_publisher_worker.py`
- `app/services/deck_structure_service.py`
- `app/services/pdf_deck_extraction_service.py`
- `app/services/deck_preview_service.py`
- `app/services/slide_thumbnail_service.py`
- `app/services/smart_deck_job_service.py`
- `app/services/smart_deck_llm_service.py`
- `app/services/deck_service.py`
- `app/services/workspace_summary_service.py`
- `app/api/routes/products.py`
- `app/api/routes/deck_workflow.py`
- `app/api/routes/smart_deck.py`
- `app/api/routes/decks.py`
- `app/api/routes/slides.py`
- Any route or service serving `DeckSlide`, `DeckSlideAsset`, previews, miniatures, generated slide render schemas, workflow-state, or Smart Deck workspace data.

`presentation_miniature_service.py` is a prune candidate, but do not delete it until all callers are proven migrated and no Railway/admin tooling imports it.

## Worker Pruning Rule

A worker can be pruned only if:

1. It is not in the canonical Upload -> Smart Deck path.
2. No active route queues its job type.
3. No Railway service depends on its `WORKER_KIND`.
4. No workflow-state depends on its output.
5. No visualizer data depends on its artifacts.
6. Generation/export/admin flows are not using it.

If any answer is unknown, mark it `LEGACY/UNKNOWN - do not delete yet`.

## Verification Commands

Local commands:

```bash
python scripts/verify_production_contract.py
python -m pytest tests/test_production_route_contract.py
python -m pytest tests/test_deck_artifacts_route.py
python -m pytest tests/test_source_pipeline_optional_brand_contract.py
python -m pytest tests/test_smart_deck_route_security.py
python -m pytest tests/test_deck_generation_route_security.py
```

Targeted local checks for Phase 1:

```bash
python -m pytest tests -k "workflow_state or smart_deck or source_pipeline or deck_artifacts"
```

Railway log checks:

```text
railway logs --service worker-source-ingestion
railway logs --service worker-source-extraction
railway logs --service worker-miniatures
railway logs --service worker-smart-deck-context
railway logs --service worker-db-publisher
railway logs --service backend
```

What to prove in logs/database:

- Upload creates one source pipeline run for the deck/source checksum.
- `source_ingestion` completes once per source checksum.
- `source_extraction` completes once and persists `DeckSlide` / `DeckSlideBlock` records.
- `miniatures` completes once and persists preview/thumbnail data for existing slides.
- `smart_deck_context` completes once and writes source workspace/source version artifacts.
- `db_publisher` is the only stage publishing `smart_deck_ready`.
- `brand_extraction` may complete after readiness but does not block `canOpenSmartDeck`.
- `/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state` returns `canOpenSmartDeck=true` only after publisher completion.
- `/api/decks/{deck_id}/smart-deck` returns usable `sourceSlides`, workspace state, and any generated slide/render schema data expected by the frontend.

Suggested API checks after uploading a test deck:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "$BACKEND_URL/api/products/deck-aistack-codes/decks/$DECK_ID/workflow-state"
curl -sS -H "Authorization: Bearer $TOKEN" "$BACKEND_URL/api/decks/$DECK_ID/smart-deck"
curl -sS -H "Authorization: Bearer $TOKEN" "$BACKEND_URL/api/decks/$DECK_ID"
```

## Phase 1 Change Candidates

Before editing Phase 1, print call sites for:

- `transition_deck_state(... DeckState.READY ...)`
- `publish_ready_state=True`
- `extract_source_previews(`
- `render_pdf_page_thumbnail(`
- `prepare_smart_deck_source_workspace(`
- `published_phase=`

Only change call sites that violate the ownership rule. Leave diagnostics, admin read models, and compatibility routes untouched unless they mutate readiness or duplicate source preview/workspace writes.
