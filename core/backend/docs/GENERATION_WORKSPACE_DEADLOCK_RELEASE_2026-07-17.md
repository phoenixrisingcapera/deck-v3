# Generation Workspace Deadlock Fix - 2026-07-17

## PR

[#96](https://github.com/phoenixrisingcapera/deck-Aistack-backend-new/pull/96)

## Tag

`v2026.07.17-generation-workspace-deadlock-fix`

## Problem

Three independent code paths created `DeckGenerationWorkspace` rows for the same deck without coordination:

1. `smart_deck_context.py` — source-context ingestion
2. `deck_mutation_service.py` — Smart Edit slide versioning
3. `deck_generation_service.py` — LLM generation service

Under concurrent worker or direct requests, each path performed a query-then-insert that could race, producing duplicate workspace rows or PostgreSQL deadlocks.

## Solution

Replace all three paths with a single idempotent `ensure_generation_workspace()` service in `app/services/deck_processing/generation_workspace_service.py`. The service uses SELECT FOR UPDATE with an explicit lock order to prevent races. Callers pass a `generation_status` and optional `id_prefix`.

The new service is the only creator of generation workspace rows in the application.

## Files Changed

- `app/services/deck_processing/generation_workspace_service.py` (new)
- `tests/test_generation_workspace_service.py` (new, 2 tests)
- `app/services/deck_processing/deck_mutation_service.py`
- `app/services/deck_processing/smart_deck_context.py`
- `app/services/llm/deck_generation_service.py`

## Verification

- 2 focused tests passed
- `python3 -m compileall -q app` passed
- `git diff --check` passed
- Railway deploy succeeded
- Production health: ok, product-ready (core, ai, storage, qwen)

## Rollback

Revert the merge commit. The three independent workspace creation paths will be restored.
