# Smart Deck Pipeline File Audit

Purpose: document what each Smart Deck pipeline file owns, and flag incomplete or duplicate responsibilities that make debugging harder.

## Current Canonical Flow

1. `app/services/deck_processing/workflow_orchestration.py` queues source jobs for an uploaded deck.
2. `app/services/deck_processing/workflow_jobs.py` defines job types, job order, dependency wiring, and status transitions.
3. `app/workers/dispatch/worker_runtime_service.py` claims ready jobs and dispatches them with heartbeat/recovery.
4. `app/workers/dispatch/job_handlers.py` routes job types to runtime handlers.
5. `app/workers/runtime/source_pipeline_runtime.py` executes source ingestion, extraction, miniatures, brand extraction, Smart Deck context preparation.
6. `app/services/deck_processing/smart_deck_context.py` creates the current source_v1 Smart Deck workspace baseline.
7. `app/workers/runtime/generation_runtime.py` executes LLM generation, validation, preview, apply, and final compile jobs.

## File Ownership Notes

- `source_pipeline_runtime.py`: workflow-stage handler only; should not contain provider-specific LLM prompt logic.
- `smart_deck_context.py`: current source workspace compiler; should become or feed the canonical `smart_deck_context` artifact.
- `generation_runtime.py`: generation workflow wrapper; should refuse evidence-bound generation when Smart Deck context is missing.
- `selected_slide_generation_runtime.py`: targeted batch manifest wrapper that resolves the configured provider and records batch results.
- `selected_slide_generation_service.py`: batching helper that now calls the configured LLM provider when available and normalizes source fact citations.
- `workflow_jobs.py`: workflow contract and dependency graph; should not contain business-stage logic.
- `worker_runtime_service.py`: durable job claiming and recovery; should not know how individual stages work.
- `job_handlers.py`: routing table only; duplicated behavior belongs in shared service modules.

## Incomplete Or Risky Areas

- `selected_slide_generation_service.summarize_slide_generation_result` now calls the LLM when credentials exist, but it still writes manifest-shaped output rather than final `SmartDeckSuggestion` rows.
- `prepare_smart_deck_source_workspace` creates source_v1 workspace artifacts, but not yet one canonical artifact with `artifact_type = "smart_deck_context"`.
- `GET /api/decks/{deck_id}/smart-deck/context` is now implemented on the Smart Deck router. It returns deck, slides, thumbnails, brand profile, deck map, source facts, `ready_for_llm`, and detailed readiness flags.
- Existing Smart Deck generation enqueue routes now reject requests until minimum deterministic Smart Deck context is ready. `POST /api/decks/{deck_id}/smart-deck/generate` now exists as a compatibility alias for the durable `/smart-deck/generation-jobs` path.
- `POST /api/suggestions/{suggestion_id}/accept` and `/reject` are now implemented. Accepted Smart Edit suggestions apply through the existing audited mutation path and also create a `DeckSlideVersion` record; rejected suggestions preserve the original slide.

## Duplicate Or Overlapping Areas

- `selected_slide_generation` appears to be the active replacement for the old `llm_parallelization` concept. Keep the batching contract, but avoid adding another parallelization runtime until SmartDeckContext is canonical.
- Source label enrichment in `smart_deck_context.py` and any future agent-based classification can overlap. The rule should be: deterministic labels/source facts first, optional agent enrichment second, one compiled context artifact last.
- Brand extraction is already a working dedicated workflow stage. Do not duplicate it inside agent code; instead, load its profile into SmartDeckContext.

## Implementation Rule Going Forward

No worker should write isolated summaries or temporary JSON that the UI cannot trace. Every output that affects Smart Deck should be attached to deck/job context and either be part of, or feed into, the canonical SmartDeckContext artifact.
