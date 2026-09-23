# Backend Cleaning Stage 1

Date: 2026-07-03

Scope: documentation only. No runtime behavior changes.

## 1. Canonical Upload To Smart Deck Path

The current MVP backend path should be understood as this pipeline:

```text
Upload deck
-> queue workflow
-> source ingestion
-> source extraction
-> miniatures / previews
-> Smart Deck context
-> db_publisher marks ready
-> workflow-state returns canOpenSmartDeck=true
-> frontend visualizer loads slides / previews
```

| Stage | Route file | Endpoint | Service called | Workflow job created | Worker that processes it | Output produced | Next stage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Upload deck | `app/api/routes/products.py` | `POST /api/products/deck-aistack-codes/decks/upload` | product upload helpers in `workspace_summary_service.py`, storage in `upload_storage.py` | none directly when manual-start path is used; deck and source file are created first | none | persisted deck row, `DeckFile`, upload metadata, Create Smart Deck CTA | queue workflow |
| Queue workflow | `app/api/routes/deck_workflow.py` and `app/api/routes/products.py` | `POST /api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/prepare`, `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction`, product start/retry routes | `app/services/deck_workflow_service.py::queue_source_extraction` | `source_ingestion`, `source_extraction`, `miniatures`, `smart_deck_context`, `db_publisher`, `brand_extraction` | none yet | durable workflow jobs and dependencies | source ingestion |
| Source ingestion | none directly; worker stage only | job type `source_ingestion` | `app/workers/source_pipeline_runtime.py::handle_source_ingestion` | already created by queue stage | source worker kind or generic queue worker dispatching source jobs | `source_file_saved`, workflow output for source file identity | source extraction |
| Source extraction | none directly; worker stage only | job type `source_extraction` | `handle_source_extraction` -> `extract_and_persist_deck_structure()` -> `extract_pdf_deck_structure()` | already created | source worker kind | `DeckSlide`, `DeckSlideBlock`, `DeckSlideAsset` source structure; extraction run counts; `source_ready` phase output | miniatures |
| Miniatures / previews | none directly; worker stage only | job type `miniatures` | `handle_miniatures` -> `extract_source_previews()` -> `source_preview_renderer` + `source_preview_persistence` | already created | source worker kind | preview images, `source_preview` assets, thumbnail paths on slides | Smart Deck context |
| Smart Deck context | none directly; worker stage only | job type `smart_deck_context` | `handle_smart_deck_context` -> `prepare_smart_deck_source_workspace()` | already created | source worker kind | Smart Deck source workspace, source versions, artifacts, enrichment metadata | db_publisher |
| Brand extraction | optional source-path stage | job type `brand_extraction` | `handle_brand_extraction` -> brand spine/service logic | already created | source worker kind | brand profile, URL/deck-derived palette, optional enrichment | completion; should not own readiness |
| Ready publication | none directly; worker stage only | job type `db_publisher` | `app/workers/publisher_runtime.py::handle_db_publisher` | already created | db publisher worker kind | `DeckState.READY`, published workflow phase `smart_deck_ready`, final source-pipeline publish event | workflow-state |
| Workflow-state | `app/api/routes/deck_workflow.py` | `GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state` | `app/services/deck_workflow_service.py::get_deck_workflow_state` currently exposed via `app/services/deck_processing/workflow_state_read_model.py` | none | none | canonical readiness contract including `canOpenSmartDeck`, stage summaries, preview counts, failures, links | frontend visualizer |
| Visualizer data load | `app/api/routes/smart_deck.py`, `app/api/routes/decks.py`, `app/api/routes/slides.py` | `GET /api/decks/{deck_id}/smart-deck`, `GET /api/decks/{deck_id}`, `GET /api/decks/{deck_id}/slides`, `GET /api/decks/{deck_id}/slides/{slide_id}/preview` | `smart_deck_llm_service.py::get_smart_deck_workspace`, `deck_service.py` read methods, preview file route | none | none | source slides, preview URLs, signed URLs, Smart Deck workspace payload, renderable visualizer data | frontend render |

## 2. Worker Audit

| File path | Job types handled | Required for Upload -> Smart Deck | Duplicates another worker/service | Recommendation | Reason |
| --- | --- | --- | --- | --- | --- |
| `app/workers/deck_queue_worker.py` | generic queue worker shell | yes | no | KEEP | likely canonical process entrypoint in some environments |
| `app/workers/job_handlers.py` | dispatch table for all workflow job types | yes | no | KEEP | this is the clean dispatch seam and should remain dumb |
| `app/workers/source_pipeline_runtime.py` | `source_ingestion`, `source_extraction`, `miniatures`, `brand_extraction`, `smart_deck_context` | yes | yes | SPLIT | owns several product stages in one file |
| `app/workers/source_ingestion_worker.py` | `source_ingestion` wrapper | yes | yes | KEEP | wrapper likely still used by Railway worker-kind mapping |
| `app/workers/source_extraction_worker.py` | `source_extraction` wrapper | yes | yes | KEEP | wrapper likely still used by Railway worker-kind mapping |
| `app/workers/miniatures_worker.py` | `miniatures` wrapper | yes | yes | KEEP | wrapper likely still used by Railway worker-kind mapping |
| `app/workers/smart_deck_context_worker.py` | `smart_deck_context` wrapper | yes | yes | KEEP | wrapper likely still used by Railway worker-kind mapping |
| `app/workers/db_publisher_worker.py` | `db_publisher` wrapper | yes | yes | KEEP | readiness-critical worker wrapper |
| `app/workers/brand_extraction_worker.py` | `brand_extraction` wrapper | yes | yes | KEEP | main spine should include brand extraction, even if non-blocking |
| `app/workers/publisher_runtime.py` | `db_publisher`, `export` | yes for `db_publisher` | partial | KEEP | single owner of readiness publication; export can split later |
| `app/workers/generation_runtime.py` | `llm_generation`, `schema_validation`, `preview_render`, `apply_version`, `compile_final_deck` | no for source-open path, yes for later product flows | yes | SPLIT | too many generation-side concerns in one runtime |
| `app/workers/llm_generation_worker.py` | `llm_generation` wrapper | no for source-open path | yes | KEEP | likely deployed worker-kind wrapper |
| `app/workers/llm_parallelization_runtime.py` | `llm_parallelization` | no | no | KEEP | outside MVP source-open path but distinct |
| `app/workers/schema_validation_worker.py` | `schema_validation` wrapper | no | yes | KEEP | generation-side wrapper; do not prune yet |
| `app/workers/preview_render_worker.py` | `preview_render` wrapper | no for source-open path | yes | LEGACY UNKNOWN | name collides conceptually with source preview service; verify usage first |
| `app/workers/apply_version_worker.py` | `apply_version` wrapper | no for source-open path | yes | KEEP | post-generation apply flow |
| `app/workers/compile_final_deck_worker.py` | `compile_final_deck` wrapper | no for source-open path | yes | KEEP | final deck/export path |
| `app/workers/export_worker.py` | `export` wrapper | no for source-open path | yes | KEEP | export path |
| `app/workers/stale_job_rescuer_worker.py` | stale job recovery only | yes operationally | no | KEEP | needed to recover stuck jobs |
| `app/workers/__init__.py` | package marker | unknown | no | KEEP | harmless package file |

## 3. Route Audit

Only routes related to upload, deck workflow, processing, preview, smart deck, or products are listed here.

| File path | Endpoint family | What it does | Queues processing | Frontend likely uses it | Recommendation |
| --- | --- | --- | --- | --- | --- |
| `app/api/routes/products.py` | `/api/products/deck-aistack-codes/*` | product upload, workspace decks, manual Smart Deck start, retry, processing links | yes | yes | KEEP as canonical product upload surface |
| `app/api/routes/deck_workflow.py` | `/api/products/deck-aistack-codes/decks/*/workflow-*` | canonical workflow-state and workflow commands | yes | yes | KEEP as canonical readiness contract |
| `app/api/routes/smart_deck.py` | `/api/decks/{deck_id}/smart-deck*` | Smart Deck workspace, generation, preferences, assistant, generated slide code | yes for generation/apply wrappers | yes | KEEP |
| `app/api/routes/decks.py` | `/api/decks/*` | deck graph, status, slides, blocks, retries, exports, legacy upload/create deck functions | yes in some endpoints | yes | KEEP for now, but simplify later |
| `app/api/routes/slides.py` | `/api/decks/{deck_id}/slides*` | source slide list and source preview file serving | no | yes | KEEP, visualizer-critical |
| `app/api/routes/blocks.py` | `/api/decks/{deck_id}/slides/{slide_id}/blocks`, patch block | no | maybe | KEEP until frontend usage is fully mapped |
| `app/api/routes/deck_intake.py` | `/api/products/deck-aistack-codes/decks/*` intake/status/structure/workspace helpers | yes | maybe | LEGACY UNKNOWN; isolate later |
| `app/api/routes/product_upload_compat.py` | compatibility product upload endpoints | maybe | likely | PRUNE LATER candidate | verify frontend and Railway usage first |
| `app/api/routes/deck_retry_rescue.py` | retry rescue endpoints | yes | maybe | PRUNE LATER candidate | rescue surface; keep until failure recovery is stabilized |
| `app/api/routes/upload_rescue.py` | upload rescue/status helpers | yes | maybe | PRUNE LATER candidate | likely incident support surface |
| `app/api/routes/deck_artifacts.py` | artifacts for deck/workflow | no | likely | KEEP | visualizer/admin artifact visibility |
| `app/api/routes/brand_extraction.py` | brand extraction endpoints | yes or async brand actions | maybe | KEEP | main spine should include brand extraction |
| `app/api/routes/shell.py` | shell/workspace endpoints | maybe | yes | KEEP | active frontend shell surface |
| `app/api/routes/exports.py` | export endpoints | yes | yes | KEEP |
| `app/api/routes/product_runtime_hardening.py` | runtime hardening helpers | no | unknown | LEGACY UNKNOWN | verify actual usage before pruning |

## 4. Service Ownership Audit

| File path | Current responsibility | What it should own | What it must not own | Duplicate responsibility found | Target folder |
| --- | --- | --- | --- | --- | --- |
| `app/services/workflow_job_service.py` | workflow job types, dependencies, idempotency, publisher rules | durable workflow contract | frontend read model or stage business logic | no major duplicate, but phase naming overlaps naturally | `app/services/deck_processing/` |
| `app/services/deck_workflow_service.py` | queueing workflow jobs and building workflow-state | queue commands plus workflow-state implementation until split | worker execution, extraction, preview rendering, Smart Deck workspace writes | yes, command + read-model mixed | `app/services/deck_processing/` |
| `app/services/deck_processing_worker_service.py` | worker-kind config, claiming, heartbeat, recovery shell | worker runtime shell | product stage logic | no direct duplicate, but helper scope is broad | `app/workers/` |
| `app/services/deck_structure_service.py` | source structure persistence plus source structure readback | source structure persistence only after split | workflow-state reads, visualizer-facing source structure read model long-term | yes, write + read model mixed | `app/services/deck_processing/` |
| `app/services/pdf_deck_extraction_service.py` | deterministic PDF structure extraction | extraction/parsing only | DB writes, previews, readiness | thumbnail helper overlap only | `app/services/deck_processing/` |
| `app/services/deck_preview_service.py` | render/persist source previews | canonical miniature generation entrypoint | readiness publication, Smart Deck workspace prep | overlaps with naming shim `presentation_miniature_service.py` | `app/services/visualizer/` or `deck_processing/` |
| `app/services/deck_processing/source_preview_renderer.py` | render preview image bytes/files | preview rendering only | persistence or readiness | no | `app/services/deck_processing/` |
| `app/services/deck_processing/source_preview_persistence.py` | save preview assets and thumbnail paths | preview persistence only | rendering or readiness | no | `app/services/deck_processing/` |
| `app/services/presentation_miniature_service.py` | wrapper around preview service | nothing long-term beyond legacy shim | canonical preview ownership | yes | prune later after verification |
| `app/services/slide_thumbnail_service.py` | low-level thumbnail helper for PDF page | helper only | canonical source preview ownership | conceptual overlap with preview renderer | `app/services/visualizer/` or helper under `deck_processing/` |
| `app/services/smart_deck_job_service.py` | prepare Smart Deck source workspace and source artifacts | Smart Deck context only | extraction, preview rendering, readiness | no acceptable duplicate | `app/services/deck_processing/` |
| `app/services/brand_loader_service.py` | initial/default brand profile and deterministic palette fallback | deterministic brand fallback and profile assembly inputs | readiness or preview ownership | yes with brand extraction/enrichment surfaces | `app/services/deck_processing/brand_extraction.py` |
| `app/services/brand_enrichment_service.py` | typography/logo enrichment from website/assets | optional enrichment only | readiness or canonical fallback ownership | yes with other brand surfaces | `app/services/deck_processing/brand_extraction.py` |
| `app/services/brand_extraction_service.py` | brand extraction APIs, URL palette logic, asset URLs, profile reads | brand extraction route-level and profile retrieval logic | readiness, source extraction, previews | yes, brand responsibilities spread out | `app/services/deck_processing/brand_extraction.py` and route-facing read helpers |
| `app/services/deck_service.py` | deck graph/read-model, slide read-model, status, edits, findings/suggestions | visualizer/read-model functions plus edit mutations until split | workflow-state implementation | yes, read model and mutation mixed | `app/services/visualizer/` |
| `app/services/smart_deck_llm_service.py` | Smart Deck workspace read model plus generation/orchestration helpers | split into visualizer workspace read model and LLM generation services | source extraction or readiness | yes, visualizer read model + LLM generation mixed | `app/services/visualizer/` + `app/services/llm/` |
| `app/services/smart_deck_prompt_builder.py` | prompt and source slide context building | prompt builder only | persistence or readiness | no | `app/services/llm/` |
| `app/services/smart_deck_source_enrichment_service.py` | optional source label enrichment | optional LLM enrichment | canonical extraction/persistence | no | `app/services/llm/` |
| `app/services/smart_deck_artifact_writer.py` | write Smart Deck source/generation artifacts | artifact writing | readiness | no | `app/services/llm/` |
| `app/services/upload_storage.py` | upload storage implementations and signed get/put URLs | artifact storage for uploaded/source files | product workflow logic | slight overlap with bucket artifact signing concepts | `app/services/storage/` |
| `app/services/bucket_artifact_service.py` | artifact key building and signed artifact URLs | artifact signing and storage access for bucket artifacts | workflow-state or read models | slight overlap with upload storage concepts | `app/services/storage/` |
| `app/services/storage_health_service.py` | storage health probe | storage health only | workflow logic | no | `app/services/storage/` |
| `app/services/deck_processing_visibility_service.py` | UI-friendly processing projection | optional derived processing view | canonical readiness contract | yes, overlaps workflow-state | `app/services/admin/` or fold into deck_processing read models later |
| `app/services/smart_deck_readiness_service.py` | readiness diagnostics | admin diagnostics | canonical readiness contract mutation | yes, overlaps workflow-state | `app/services/admin/` |
| `app/services/workspace_dashboard_service.py` | dashboard deck summaries and thumbnails | dashboard read model | readiness ownership | reads workflow-state and preview data | `app/services/visualizer/` or dashboard read models |
| `app/services/workspace_summary_service.py` | product workspace summaries, welcome state, upload-adjacent deck summaries | product upload/read model support | worker logic | some deck state derivation overlap | `app/services/visualizer/` or `deck_processing/` support layer |
| `app/services/upload_service.py` | legacy upload path and state transitions | legacy upload support only | canonical product upload path if not proven used | yes, overlaps product upload surfaces | legacy / prune later |

## 5. Proposed Clean Folder Structure

```text
app/services/deck_processing/
  source_pipeline.py
  source_ingestion.py
  source_extraction.py
  source_structure_persistence.py
  source_preview_renderer.py
  source_preview_persistence.py
  smart_deck_context.py
  readiness_publisher.py
  workflow_state_read_model.py

app/services/visualizer/
  slide_read_model.py
  preview_asset_service.py
  miniature_service.py

app/services/llm/
  provider_client.py
  prompt_builder.py
  generation_service.py
  critique_service.py
  repair_service.py
  artifact_service.py

app/services/storage/
  artifact_storage.py
  signed_urls.py
  bucket_health.py

app/services/admin/
  diagnostics.py
  worker_health.py
  llm_knowledge_health.py

app/workers/
  source_worker.py
  generation_worker.py
  export_worker.py
  stale_job_rescuer.py
  job_handlers.py
```

## 6. Prune Candidates

| File path | Why it looks duplicate | What must be verified before deletion | Replacement owner |
| --- | --- | --- | --- |
| `app/services/presentation_miniature_service.py` | wrapper around `deck_preview_service.extract_source_previews()` | no route imports, no worker imports, no tests/ops scripts depend on it | `app/services/deck_preview_service.py` or `app/services/visualizer/miniature_service.py` |
| `app/api/routes/product_upload_compat.py` | compatibility upload surface next to `products.py` | frontend proxy usage, Railway smoke tests, support scripts | `app/api/routes/products.py` |
| `app/api/routes/deck_retry_rescue.py` | rescue retry surface next to workflow/product retry entrypoints | admin/support flows and failure runbooks | canonical workflow/product retry routes |
| `app/api/routes/upload_rescue.py` | rescue upload visibility surface | production incident runbooks and frontend usage | canonical product upload + workflow-state |
| `app/api/routes/deck_generation.py` | older generation surface outside the cleaner workflow contract | frontend generation calls and worker job dependencies | `app/api/routes/smart_deck.py` + `deck_workflow.py` |
| `app/api/routes/deck_intake.py` | mixed intake/status/structure helpers alongside product/workflow routes | active frontend usage of status/structure/due diligence helpers | product + workflow + dedicated read-model routes already in use |
| `app/services/upload_service.py` | older upload/state logic parallel to product upload flows | route imports, worker imports, smoke tests | `workspace_summary_service.py` + `upload_storage.py` + product routes |
| `app/workers/preview_render_worker.py` | generation-side preview name collides conceptually with source miniatures | active generation flow job types and Railway worker kind | generation runtime or future generation worker |

If any verification is unknown, the file remains `LEGACY UNKNOWN` and must not be deleted yet.

## 7. Do-Not-Delete-Yet List

These files are on the active Upload -> Smart Deck path or directly support the visualizer and must be protected:

- `app/api/routes/products.py`
- `app/api/routes/deck_workflow.py`
- `app/api/routes/smart_deck.py`
- `app/api/routes/decks.py`
- `app/api/routes/slides.py`
- `app/services/workflow_job_service.py`
- `app/services/deck_workflow_service.py`
- `app/services/deck_processing_worker_service.py`
- `app/workers/job_handlers.py`
- `app/workers/source_pipeline_runtime.py`
- `app/workers/publisher_runtime.py`
- `app/workers/source_ingestion_worker.py`
- `app/workers/source_extraction_worker.py`
- `app/workers/miniatures_worker.py`
- `app/workers/smart_deck_context_worker.py`
- `app/workers/db_publisher_worker.py`
- `app/workers/brand_extraction_worker.py`
- `app/services/deck_structure_service.py`
- `app/services/pdf_deck_extraction_service.py`
- `app/services/deck_preview_service.py`
- `app/services/deck_processing/source_preview_renderer.py`
- `app/services/deck_processing/source_preview_persistence.py`
- `app/services/smart_deck_job_service.py`
- `app/services/deck_service.py`
- `app/services/smart_deck_llm_service.py`
- `app/services/upload_storage.py`
- `app/services/bucket_artifact_service.py`
- any file that creates, stores, reads, signs, or serves `DeckSlide`, `DeckSlideAsset`, preview images, Smart Deck workspace payloads, or workflow-state responses

## 8. Commands I Can Run

Verify imports still work:

```bash
python3 -m py_compile app/main.py app/services/deck_workflow_service.py app/workers/source_pipeline_runtime.py app/workers/publisher_runtime.py
python3 -m py_compile app/services/deck_preview_service.py app/services/deck_structure_service.py app/services/smart_deck_job_service.py app/services/deck_service.py app/services/smart_deck_llm_service.py
```

Verify API starts:

```bash
python3 -m uvicorn app.main:app --reload
```

Verify upload route exists:

```bash
python3 scripts/verify_production_contract.py
```

Verify workflow-state route exists:

```bash
python3 scripts/verify_production_contract.py
curl -sS "$BACKEND_URL/api/products/deck-aistack-codes/decks/$DECK_ID/workflow-state" -H "Authorization: Bearer $TOKEN"
```

Verify worker can process source jobs:

```bash
python3 -m pytest tests/test_source_pipeline_optional_brand_contract.py
python3 -m pytest tests/test_deck_preview_service.py
python3 -m pytest tests/test_smart_deck_source_orchestration.py
```

Verify visualizer receives slide/preview data:

```bash
curl -sS "$BACKEND_URL/api/decks/$DECK_ID" -H "Authorization: Bearer $TOKEN"
curl -sS "$BACKEND_URL/api/decks/$DECK_ID/slides" -H "Authorization: Bearer $TOKEN"
curl -sS "$BACKEND_URL/api/decks/$DECK_ID/smart-deck" -H "Authorization: Bearer $TOKEN"
curl -I "$BACKEND_URL/api/decks/$DECK_ID/slides/$SLIDE_ID/preview" -H "Authorization: Bearer $TOKEN"
```

Recommended Railway log checks:

```bash
railway logs --service worker-source-ingestion
railway logs --service worker-source-extraction
railway logs --service worker-miniatures
railway logs --service worker-smart-deck-context
railway logs --service worker-db-publisher
railway logs --service worker-brand-extraction
railway logs --service backend
```

What to prove in logs:

- upload persisted source file once
- source workflow jobs were queued once per source checksum
- `source_extraction` completed and wrote slides/assets
- `miniatures` completed and wrote preview assets
- `smart_deck_context` completed and prepared source workspace
- `db_publisher` was the only readiness publisher for `smart_deck_ready`
- workflow-state returned `canOpenSmartDeck=true`
- visualizer routes served slide and preview data successfully
