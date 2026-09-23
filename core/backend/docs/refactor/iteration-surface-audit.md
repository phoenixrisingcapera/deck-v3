# Iteration Surface Audit

## Canonical Iteration Surface

The current persisted iteration flow is the `DesignBatch` product contract exposed as `/versions`.

Internal note: when older code or storage still says `batch`, read it as persisted `iteration` unless the context is explicitly low-level execution batching.

- Backend persistence remains on `design_batches`, `design_batch_slides`, `generated_slide_candidates`, `batch_slide_decisions`, and `compiled_decks`.
- Product routes already expose this flow as `/api/products/deck-aistack-codes/decks/{deck_id}/versions`.
- Frontend `/decks/.../batches/...` pages and `/api/decks/.../batches/...`
  proxies are compatibility aliases only. Canonical product pages and active
  links use `/iterations`, including iteration review and compile/finalization.

## Duplicate Version Surfaces

There are still two real user-facing version systems that overlap and must be reconciled before deleting more compatibility code.

### DesignBatch / Iteration History

- Review-first persisted iteration history.
- Whole-deck and selected-slide iteration creation.
- Candidate review with explicit keep-version or keep-original decisions.
- Final deck compilation from accepted iteration decisions.

Primary code:

- `app/services/platform/shell/shell_service.py`
- `app/services/rendering/final_deck_service.py`
- `app/api/routes/shell.py`

### DesignVersion / Smart Deck Workspace

- Smart Deck preview and compare workspace.
- Apply, discard, and restore operations on generated design versions.
- Active version state stored in Smart Deck preferences/workspace.

Primary code:

- `app/services/llm/generation_service.py`
- `app/api/routes/smart_deck.py`
- `src/lib/components/smart-deck/SmartDeckWorkspace.svelte`

## Current Cleanup Rule

Do not rename database tables during the terminology migration.

- Use `iteration` in user-facing copy, API aliases, and cleanup docs.
- Keep DB models and tables unchanged until the `DesignBatch` and `DesignVersion` surfaces are unified.
- Treat `selected_slide_generation` as a workflow planning step, not as the canonical persisted iteration history.

## Next Merge-Safe Consolidation Steps

1. Keep `/versions` as the canonical persisted iteration API.
2. Frontend page migration is complete: keep `/batches` only as preserved
   compatibility redirects/proxies while older bookmarks or callers may exist.
3. Replace `parallelization` request naming with `selectedSlideGeneration`.
4. Decide whether Smart Deck should write directly into the persisted iteration history or whether iteration history should read from the Smart Deck version model.
