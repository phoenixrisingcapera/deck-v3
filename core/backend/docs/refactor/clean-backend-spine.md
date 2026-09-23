# Clean Backend Spine For DeckAiStack

Date: 2026-07-03

Branch: `backend-ownership-audit-docs`

Scope: staged refactor plan before any new spine migration work. This document does not add routes, features, or runtime behavior.

## Refactor Or Rebuild?

This should be a refactor, not a rebuild.

Reason:

- The backend already has working core pieces for the MVP path: upload entrypoints, durable workflow jobs, worker dispatch, source extraction, preview rendering, Smart Deck context preparation, readiness publishing, workflow-state, and visualizer-facing read models.
- The main problem is not absence of implementation. The main problem is duplicate ownership and too many parallel surfaces.
- A full rebuild would risk breaking the product-critical visualizer path: `DeckSlide`, `DeckSlideAsset`, source previews, signed URLs, workflow-state, and Smart Deck workspace payloads.

The right approach is a strangler refactor:

1. Define the clean backend spine.
2. Move current working logic into single-owner folders.
3. Route the MVP through the clean spine.
4. Prove the visualizer still works.
5. Only then prune leftovers.

## Plain English Explanation

The backend should behave like a factory line.

- Upload receives the file.
- Workflow creates the list of jobs.
- Source ingestion confirms the file exists and is attached to a workflow run.
- Source extraction reads the deck and writes slide structure.
- Brand extraction prepares the brand profile/materials needed by the product from the same uploaded deck context.
- Brand extraction should prefer company URL signals when available, fall back to deck-derived brand signals when URL extraction is unavailable, and preserve the deck's deterministic color palette by default.
- Miniatures turns existing source slides into preview images.
- Smart Deck context prepares the source workspace the Smart Deck UI needs.
- `db_publisher` is the only stage allowed to mark the deck ready.
- Workflow-state is the one backend answer the frontend trusts for whether Smart Deck can open.
- Visualizer/read-model services serve slides, previews, and workspace payloads.

Today the backend feels messy because several files still do more than one factory job or expose old wrapper names for the same job.

Brand extraction should be understood as a supporting spine stage, not a second readiness publisher. It belongs in the main spine because the product benefits from consistent brand context, but it must not become another owner of extraction, preview rendering, Smart Deck workspace preparation, or final readiness publication.

## What Code Is Worth Keeping

These pieces are worth keeping and reorganizing:

- `app/services/workflow_job_service.py`
  The durable job contract.
- `app/services/deck_workflow_service.py`
  The queueing plus workflow-state read model, though it should be split later.
- `app/services/deck_processing_worker_service.py`
  The worker shell and claiming logic.
- `app/workers/job_handlers.py`
  The dispatch seam.
- `app/workers/source_pipeline_runtime.py`
  The actual source-side stage execution path.
- `app/workers/publisher_runtime.py`
  The final readiness publisher.
- `app/services/deck_structure_service.py`
  The current source structure persistence seam.
- `app/services/pdf_deck_extraction_service.py`
  The deterministic structure extractor.
- `app/services/deck_preview_service.py`
  The canonical source preview path.
- `app/services/smart_deck_job_service.py`
  The Smart Deck source context/workspace writer.
- `app/services/deck_service.py`
  A useful visualizer/read-model surface.
- `app/services/smart_deck_llm_service.py`
  Useful logic, but too broad and needs splitting.
- `app/services/upload_storage.py`
  Storage logic worth preserving.
- `app/services/bucket_artifact_service.py`
  Signed URL and artifact storage logic worth preserving.

## What Should Be Isolated

These areas should be isolated into cleaner single-owner modules:

- Worker shell concerns from worker business logic.
- Source extraction parsing from source structure persistence.
- Preview rendering from preview persistence.
- Brand profile derivation from brand signal sourcing and enrichment.
- Smart Deck source context from visualizer workspace read model.
- Workflow-state read model from queueing/orchestration commands.
- Storage primitives from product-facing services.
- LLM provider, prompt, generation, critique, repair, and artifacts from Smart Deck read surfaces.

## What Should Be Deleted Later

These are later prune candidates, not immediate deletions:

- `app/services/presentation_miniature_service.py`
  Wrapper/compatibility naming shim around the canonical preview service.
- Compatibility and rescue route surfaces once usage is proven absent.
- Wrapper worker entrypoints if Railway no longer depends on those `WORKER_KIND` names.
- Legacy upload/intake/generation surfaces once frontend and worker usage is proven removed.

Nothing should be deleted until the replacement owner exists, is active, and is verified.

## Current Upload To Smart Deck Path

```text
Upload deck
-> create workflow run
-> source ingestion
-> source extraction
-> brand extraction
-> preview / miniature rendering
-> Smart Deck context preparation
-> db_publisher marks ready
-> workflow-state says Smart Deck can open
-> frontend visualizer loads slides and previews
```

Current owner mapping:

| Product stage | Current owner |
| --- | --- |
| Upload route | `app/api/routes/products.py` plus upload/workspace services |
| Workflow run creation | `app/services/deck_workflow_service.py::queue_source_extraction` |
| Source ingestion | `app/workers/source_pipeline_runtime.py::handle_source_ingestion` |
| Source extraction | `app/workers/source_pipeline_runtime.py::handle_source_extraction` + `app/services/deck_structure_service.py` + `app/services/pdf_deck_extraction_service.py` |
| Brand extraction | `app/workers/source_pipeline_runtime.py::handle_brand_extraction` + `app/services/brand_loader_service.py` + `app/services/brand_enrichment_service.py` |
| Preview/miniatures | `app/workers/source_pipeline_runtime.py::handle_miniatures` + `app/services/deck_preview_service.py` |
| Preview persistence | `app/services/deck_processing/source_preview_persistence.py` |
| Smart Deck context | `app/workers/source_pipeline_runtime.py::handle_smart_deck_context` + `app/services/smart_deck_job_service.py` |
| Readiness publisher | `app/workers/publisher_runtime.py::handle_db_publisher` |
| Workflow-state | `app/services/deck_workflow_service.py::get_deck_workflow_state` |
| Visualizer data | `app/services/deck_service.py`, `app/api/routes/smart_deck.py`, `app/services/smart_deck_llm_service.py::get_smart_deck_workspace` |

## Current Duplicate Responsibilities

1. Workflow queueing and workflow-state live together in `deck_workflow_service.py`.

2. Source structure persistence and source structure readback live together in `deck_structure_service.py`.

3. Smart Deck read model and Smart Deck LLM generation live together in `smart_deck_llm_service.py`.

4. Source preview logic still has a duplicate naming surface in `presentation_miniature_service.py`.

5. Brand extraction is in the active source pipeline runtime, but it is not yet isolated as a first-class spine module with a single clear owner.

   Today brand behavior is spread across loader, extraction, enrichment, and route surfaces. The clean spine should merge that ownership into one brand extraction stage with explicit fallback rules.

6. `slide_thumbnail_service.py` and the preview pipeline both create slide images, though they are not the same ownership boundary.

7. Worker wrapper files and runtime files are split inconsistently: some wrappers are pure process entrypoints while runtime modules still carry multiple product stages.

8. There are multiple route families for uploads, retries, intake, rescue, and product compatibility. They should not all remain first-class long-term.

## Files That Are Active And Must Not Be Deleted Yet

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
- `app/services/deck_processing/source_preview_renderer.py`
- `app/services/deck_processing/source_preview_persistence.py`
- `app/services/smart_deck_job_service.py`
- `app/services/deck_service.py`
- `app/services/smart_deck_llm_service.py`
- `app/services/upload_storage.py`
- `app/services/bucket_artifact_service.py`
- `app/api/routes/products.py`
- `app/api/routes/deck_workflow.py`
- `app/api/routes/smart_deck.py`
- `app/api/routes/slides.py`
- Any file serving `DeckSlide`, `DeckSlideAsset`, source preview URLs, signed URLs, or workflow-state to the frontend visualizer.

## Compatibility, Rescue, Or Legacy Candidates

These are candidates for later isolation/prune review, not immediate deletion:

- `app/services/presentation_miniature_service.py`
- `app/api/routes/product_upload_compat.py`
- `app/api/routes/deck_retry_rescue.py`
- `app/api/routes/upload_rescue.py`
- `app/api/routes/product_runtime_hardening.py`
- `app/api/routes/deck_intake.py`
- `app/api/routes/deck_generation.py`
- `app/services/upload_service.py`
- Other route surfaces proven not to be used by the current frontend MVP or Railway workers

Mark any unknown dependency as `LEGACY/UNKNOWN - do not delete yet`.

## Proposed Target Folder Structure

```text
app/services/deck_processing/
  source_pipeline.py
  source_ingestion.py
  source_extraction.py
  brand_extraction.py
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

app/workers/
  source_worker.py
  generation_worker.py
  export_worker.py
  stale_job_rescuer.py
  job_handlers.py
```

## Exact Migration Plan

### Stage 1: spine planning only

- Document the clean spine.
- Do not delete runtime files.
- Do not change frontend contracts.

### Stage 2: create folders without behavior change

- Create:
  - `app/services/deck_processing/`
  - `app/services/visualizer/`
  - `app/services/llm/`
  - `app/services/storage/`
- Move internal code only where imports can be updated safely.
- Keep old imports working temporarily if needed during the migration phase.

Suggested first safe moves:

- `app/services/pdf_deck_extraction_service.py` -> `app/services/deck_processing/source_extraction.py`
- `app/services/brand_loader_service.py` + `app/services/brand_enrichment_service.py` + source-runtime brand orchestration + brand fallback rules -> `app/services/deck_processing/brand_extraction.py`
- `app/services/deck_processing/source_preview_renderer.py` stays under `deck_processing/`
- `app/services/deck_processing/source_preview_persistence.py` stays under `deck_processing/`
- `app/services/deck_preview_service.py` -> `app/services/visualizer/miniature_service.py` or `deck_processing/source_pipeline.py` depending on final seam
- `app/services/upload_storage.py` -> `app/services/storage/artifact_storage.py`
- `app/services/storage_health_service.py` -> `app/services/storage/bucket_health.py`

### Stage 3: separate ownership by concern

- Split `deck_structure_service.py` into:
  - `deck_processing/source_structure_persistence.py`
  - `visualizer/slide_read_model.py` or a source read-model helper

- Split `deck_workflow_service.py` into:
  - source/workflow command queueing
  - `deck_processing/workflow_state_read_model.py`

- Split `smart_deck_llm_service.py` into:
  - visualizer/read-model workspace loader
  - LLM generation service
  - provider/config resolution
  - artifacts
  - prompt assembly

- Merge brand task ownership into one module:
  - URL-based brand signal loading
  - deck-derived deterministic palette fallback
  - optional ML/LLM enrichment of brand profile
  - final brand profile assembly used by product surfaces

### Stage 4: narrow worker responsibilities

- `source_pipeline_runtime.py` should eventually become:
  - `deck_processing/source_ingestion.py`
  - `deck_processing/source_extraction.py`
  - `deck_processing/brand_extraction.py`
  - `visualizer/miniature_service.py` or `deck_processing/source_pipeline.py`
  - `deck_processing/smart_deck_context.py`

- Workers should dispatch jobs, not secretly own the product rules.

### Stage 5: prune only after proof

- Remove wrapper/shim files only after:
  - no route imports them
  - no worker imports them
  - no workflow job depends on them
  - no frontend endpoint depends on them
  - no visualizer data depends on them
  - no Railway worker kind depends on them
  - the replacement owner exists and is verified

## Worker Pruning Plan

Worker families should converge toward:

- `source_worker.py`
  - claims and dispatches source-side jobs: source ingestion, source extraction, brand extraction, miniatures, and Smart Deck context
- `generation_worker.py`
  - claims and dispatches generation/apply/schema/preview-render jobs
- `export_worker.py`
  - claims export/final-publish oriented jobs
- `stale_job_rescuer.py`
  - recovery only
- `job_handlers.py`
  - remains the dispatch seam

Prune order:

1. Audit active Railway `WORKER_KIND` names.
2. Map each to active job types.
3. Consolidate startup wrappers only after Railway services are updated.
4. Remove only wrappers proven redundant.

Do not prune `miniatures`, `smart_deck_context`, or `db_publisher` wrappers until the consolidated worker mapping is proven in Railway.

## Visualizer Verification Plan

The visualizer is the highest-risk area. Every migration stage must prove:

1. `DeckSlide` rows still exist and remain queryable.
2. `DeckSlideAsset` rows for `source_preview` still exist.
3. Slide preview URLs still resolve.
4. Signed URLs still resolve when used.
5. Workflow-state still returns:
   - phase
   - next action
   - source counts
   - `canOpenSmartDeck`
6. Smart Deck workspace still loads source slides and preview data.
7. Brand fallback behavior remains stable:
   - URL brand signals are used when available
   - deterministic deck colors are preserved when URL extraction is unavailable
   - optional ML/LLM enrichment improves brand profile without breaking the default deterministic palette

Suggested verification commands:

```bash
python3 -m pytest tests/test_deck_preview_service.py
python3 -m pytest tests/test_smart_deck_source_orchestration.py
python3 -m pytest tests/test_source_pipeline_optional_brand_contract.py
python3 -m pytest tests/test_deck_artifacts_route.py
python3 -m pytest tests/test_production_route_contract.py
```

Suggested API checks:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" "$BACKEND_URL/api/products/deck-aistack-codes/decks/$DECK_ID/workflow-state"
curl -sS -H "Authorization: Bearer $TOKEN" "$BACKEND_URL/api/decks/$DECK_ID/smart-deck"
curl -sS -H "Authorization: Bearer $TOKEN" "$BACKEND_URL/api/decks/$DECK_ID"
curl -sS -H "Authorization: Bearer $TOKEN" "$BACKEND_URL/api/decks/$DECK_ID/slides/$SLIDE_ID/preview"
```

Suggested Railway log checks:

```text
railway logs --service worker-source-ingestion
railway logs --service worker-source-extraction
railway logs --service worker-miniatures
railway logs --service worker-smart-deck-context
railway logs --service worker-db-publisher
railway logs --service backend
```

Prove in logs:

- source extraction runs once for a source checksum
- brand extraction runs once for the workflow run and does not create duplicate readiness side effects
- brand extraction falls back cleanly from URL signals to deck-derived colors when URL sourcing fails or is unavailable
- miniatures renders once against existing source slides
- Smart Deck context prepares once
- `db_publisher` publishes readiness once
- workflow-state returns `canOpenSmartDeck=true` only after publisher completion

## Staged PR Plan

### PR 1: ownership enforcement

- Make `db_publisher` the only source-pipeline readiness publisher.
- Make miniatures the only source preview renderer.
- Keep Smart Deck context as the only source workspace writer.
- Keep brand extraction in the main spine, but ensure it owns only brand profile work and does not duplicate extraction, preview, workspace, or readiness ownership.

Brand extraction rule for the spine:

- Use company URL signals first when available.
- If URL extraction is not possible, derive and preserve the main colors from the deck deterministically.
- Allow optional ML/LLM enrichment to improve the brand profile, but do not require it for baseline brand colors.
- Keep brand extraction non-blocking for `canOpenSmartDeck` unless product requirements explicitly change later.

### PR 2: folder creation without behavior change

- Add clean folders.
- Move code with import updates only.
- No route changes.

### PR 3: split overloaded services

- Split workflow-state from queueing.
- Split source persistence from source readback.
- Split Smart Deck workspace/read-model code from LLM generation code.

### PR 4: consolidate worker startup wrappers

- Update Railway worker mapping.
- Consolidate wrappers only after proof.

### PR 5: route and file pruning

- Remove compatibility/rescue/legacy files only after usage proof and replacement verification.

### PR 6: final visualizer hardening

- Re-verify slides, previews, workspace payloads, and degraded/failure behavior.

## Recommended Direction

Do not rebuild from scratch.

Create a clean backend spine and migrate the current working logic into it, one responsibility at a time.

That gives you a backend that is easier to reason about without throwing away the working pieces that already support the MVP visualizer.
