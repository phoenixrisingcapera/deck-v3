# Processing state contract

## Goal

The processing page must read one canonical backend state object instead of assembling page state from upload, deck list, brand profile, Smart Deck prefetch, and workspace-provider calls.

## Endpoint

```text
GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state
```

## Required response fields

```json
{
  "deckId": "deck_...",
  "workflowId": "deckwf_...",
  "phase": "source_extraction_running",
  "status": "running",
  "nextAction": "wait_for_processing",
  "blockingReason": null,
  "canOpenSmartDeck": false,
  "canRetry": false,
  "activeJob": {},
  "latestJobs": [],
  "source": {},
  "smartDeck": {},
  "provider": {},
  "links": {},
  "updatedAt": "2026-06-27T12:00:00Z"
}
```

Compatibility `/processing` may still project a browser-friendly summary over
the canonical workflow payload.

## Product rules

- Open Smart Deck only when `nextAction === "open_smart_deck"` or `canOpenSmartDeck === true`.
- Show retry only when `nextAction === "retry_or_manual_review"` or `canRetry === true`.
- Remove/delete actions should remain disabled while `canRemove === false`.
- The processing page should not rely on workspace AI provider state.
- The processing page should not prefetch Smart Deck data before the backend says it is ready.
- `workflow-state` is canonical; `/processing` is compatibility only.
