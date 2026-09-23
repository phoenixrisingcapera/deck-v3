# Backend Upload -> Smart Deck MVP Audit

This audit is intentionally narrow. It covers only the active backend files that
shape the Upload -> Smart Deck MVP path and focuses on ownership, overlap, and
prune readiness.

## MVP Ownership Target

```text
source_extraction   -> extracts and persists source structure
miniatures          -> renders and persists source previews
smart_deck_context  -> prepares Smart Deck source workspace
db_publisher        -> marks Smart Deck ready
workflow-state      -> tells the frontend when Smart Deck can open
```

## Audit Table

| File path | Current responsibility | MVP relevance | Duplicate responsibility | Recommended action | Risk level | What to learn from this file |
| --- | --- | --- | --- | --- | --- | --- |
| `app/services/deck_workflow_service.py` | Builds the canonical workflow-state read model from deck rows, workflow jobs, failure tickets, worker heartbeat, source slides/assets, and generation state. | Critical. This is the backend truth the frontend should trust. | Some source-enrichment/workspace shaping overlaps conceptually with `smart_deck_job_service.py`, but here it is read-model projection, not write ownership. | KEEP. Treat it as the only readiness read contract and keep pushing UI logic toward this boundary. | High. Changes here alter what the product believes about readiness and failure. | Learn how to build a canonical read model from multiple write models without letting the frontend infer state for itself. |
| `app/services/workflow_job_service.py` | Defines job types, sequence order, dependencies, idempotency, status transitions, artifacts, and publisher-only final phases. | Critical. This is the contract that turns source processing into a durable pipeline. | Phase naming overlaps with `deck_workflow_service.py`, but this file owns raw job semantics while `deck_workflow_service.py` maps them for product reads. | KEEP. This should remain the single source of truth for source-pipeline order and publish permissions. | High. Sequence or status drift here breaks every worker and the workflow-state contract. | Learn to separate orchestration primitives from business logic; constants and dependency graphs belong in one place. |
| `app/services/deck_processing_worker_service.py` | Configures worker kinds, claimable job types, heartbeat threads, stale recovery, and dispatch into runtime handlers. | Critical for production execution, but indirect for product behavior. | Some phase/failure marking overlaps with runtime modules because it owns generic recovery helpers used by handlers. | KEEP. Long-term split helper functions if this file keeps absorbing stage-specific behavior. | High. Misconfiguring worker kind or job claiming silently stalls the whole source pipeline. | Learn the difference between worker shell concerns and stage logic. Heartbeats, claiming, and recovery are infrastructure, not product logic. |
| `app/workers/job_handlers.py` | Minimal registry mapping each `job_type` to the correct runtime function. | Important as a seam, but intentionally small. | None meaningful; this is the dispatch table. | KEEP. Resist adding logic here. | Low. The danger is accidental logic growth, not current complexity. | Learn to keep dispatch seams dumb. A clean registry makes ownership obvious. |
| `app/workers/source_pipeline_runtime.py` | Executes `source_ingestion`, `source_extraction`, `miniatures`, `brand_extraction`, and `smart_deck_context` jobs and writes workflow-job outputs for each stage. | Critical. This is the source-side runtime path the MVP depends on. | `brand_extraction` lives in the same runtime even though it is not core to Smart Deck readiness; that is an orchestration convenience, not ideal ownership. | KEEP. Preserve the current stage split: extraction -> miniatures -> smart_deck_context. Consider pruning or reordering brand later only after product proof. | High. This file is where stage boundaries are either enforced or accidentally re-blurred. | Learn how stage handlers should do one unit of work, emit clear outputs, and stop before the next stage’s responsibility begins. |
| `app/workers/publisher_runtime.py` | Publishes final workflow phases and moves deck state to `ready`; also records export artifacts. | Critical. This is the only place that should mark `smart_deck_ready`. | None acceptable for MVP; if any other service marks readiness, that is a bug. | KEEP. Preserve strict ownership of final publish here. | High. Duplicate ready publication is one of the main causes of product confusion. | Learn why final publication needs a single owner. Distributed “ready” writes create race conditions and UI lies. |
| `app/services/deck_structure_service.py` | Clears old source structure, persists `DeckSlide`, `DeckSlideBlock`, and `DeckSlideAsset` rows from extracted payloads, and exposes deck structure views. | Critical, but overloaded. It is the main persistence seam for source extraction. | Its write path duplicates concerns that should eventually live in a narrower `source_structure_persistence.py`. It also carries a large read-model helper surface. | SPLIT LATER. Keep behavior, but refactor toward a thinner orchestration layer plus dedicated persistence module in a future PR. | High. Clearing and rebuilding source structure can destroy downstream state if ownership is not explicit. | Learn to distinguish parsing, persistence, and readback. When one file does all three, it becomes hard to reason about side effects. |
| `app/services/pdf_deck_extraction_service.py` | Extracts deterministic PDF structure in memory: page metadata, text, OCR fallback, embedded assets, and optional thumbnail payloads. | Critical. This is the canonical structure extractor for PDF-backed source extraction. | Thumbnail generation overlaps with `slide_thumbnail_service.py` by design because it delegates there when thumbnails are requested. | KEEP. Continue calling it with `include_thumbnails=False` for the MVP source path so miniatures remains the canonical preview stage. | Medium. The danger is not the extractor itself; it is accidentally turning thumbnails back on in source extraction. | Learn to keep parsing pure when possible. Return structured payloads first; persist them somewhere else. |
| `app/services/deck_preview_service.py` | Renders page previews and persists `source_preview` assets onto existing source slides. | Critical. This is the canonical miniatures implementation. | Historical naming overlap with `presentation_miniature_service.py`, which now only delegates here. | KEEP. This should remain the single preview rendering/persistence entry point for the source pipeline. | High. If preview creation migrates back into extraction or another wrapper, readiness and slide ownership drift again. | Learn the benefit of requiring existing source slides before preview generation. It forces the correct stage order. |
| `app/services/presentation_miniature_service.py` | Validates PDF/PPT/PPTX source type and delegates directly to `deck_preview_service.extract_source_previews()`. | Low for MVP behavior. It is no longer the canonical worker path. | Near-total duplication with `deck_preview_service.py`; its only unique behavior is extension validation plus old naming. | PRUNE CANDIDATE. Do not delete in this audit, but remove callers first in a separate PR. | Medium. Keeping it around is mostly a readability risk, not an immediate production risk. | Learn to spot wrapper files that survive a refactor even after the real ownership moved elsewhere. |
| `app/services/slide_thumbnail_service.py` | Uses `pdftoppm` to render lightweight thumbnail files for a single PDF page. | Secondary for the MVP path because source extraction currently disables thumbnail rendering. | Conceptually overlaps with `deck_preview_service.py` because both create images of source pages, but they serve different contracts today. | SPLIT LATER. Keep it until the extractor no longer needs optional thumbnail support or there is a unified image strategy. | Medium. It can reintroduce duplicate rendering paths if called casually from source extraction. | Learn to separate “file renderer helper” from “product preview contract.” Similar outputs do not always mean identical responsibilities. |
| `app/services/smart_deck_job_service.py` | Builds the Smart Deck source workspace, source generation run, source versions, and source artifacts from persisted extracted slides. | Critical. This is the canonical source workspace writer. | Some semantic labeling logic overlaps conceptually with earlier extraction metadata, but this file owns the Smart Deck baseline, not raw extraction. | KEEP. Protect it as the only `smart_deck_context` writer in the MVP path. | High. If extraction starts preparing the workspace again, the source pipeline becomes ambiguous immediately. | Learn the difference between “source structure exists” and “Smart Deck workspace is prepared.” They are separate states and should stay separate. |

## Main Duplications To Watch

1. `deck_structure_service.py` is still overloaded.
   It currently mixes destructive cleanup, source-structure persistence, and
   structure readback helpers. That is the main future split point.

2. `presentation_miniature_service.py` is now mostly a naming wrapper.
   The canonical miniatures implementation lives in `deck_preview_service.py`.

3. `slide_thumbnail_service.py` and `deck_preview_service.py` both create page
   images.
   They are not the same contract today, but they are easy to confuse.

4. `brand_extraction` still sits inside the source runtime even though Smart
   Deck opening should not conceptually depend on it unless the product chooses
   that behavior explicitly.

## What A New Engineer Should Understand First

1. `workflow_job_service.py`
   This is the pipeline contract. Start here to understand job ordering.

2. `source_pipeline_runtime.py`
   This is the execution path for source-side jobs.

3. `deck_structure_service.py`
   This is where extracted source structure becomes database rows.

4. `deck_preview_service.py`
   This is where existing source slides gain canonical previews.

5. `smart_deck_job_service.py`
   This is where extracted source data becomes Smart Deck workspace state.

6. `publisher_runtime.py`
   This is the only place that should turn the source pipeline into
   `smart_deck_ready`.

7. `deck_workflow_service.py`
   This is the final read model the frontend should trust.

## MVP Reading Order

```text
workflow_job_service.py
  -> source_pipeline_runtime.py
  -> deck_structure_service.py
  -> pdf_deck_extraction_service.py
  -> deck_preview_service.py
  -> smart_deck_job_service.py
  -> publisher_runtime.py
  -> deck_workflow_service.py
```
