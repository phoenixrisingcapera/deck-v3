# Production API Contract

## Runtime surface

- Frontend origin: `https://deck.aistack.codes`
- Backend origin: `https://api.deck.aistack.codes`
- API prefix: `/api`

## Canonical production endpoints

### Health
- `GET /api/health`
- `GET /api/health/storage`

### Auth
- `POST /api/auth/sign-in`
- `POST /api/auth/sign-up` (compat alias kept as optional compatibility)
- `GET  /api/auth/me`

### Workspace summary
- `GET /api/products/deck-aistack-codes/welcome-state`
- `GET /api/products/deck-aistack-codes/workspace-summary`
- `GET /api/products/deck-aistack-codes/decks`

### Workspace AI provider
- `GET    /api/settings/workspace/ai-provider`
- `POST   /api/settings/workspace/ai-provider`
- `DELETE /api/settings/workspace/ai-provider`

### Deck loading
- `GET  /api/products/deck-aistack-codes/decks/{deck_id}/status`
- `GET  /api/products/deck-aistack-codes/decks/{deck_id}/structure`
- `GET  /api/products/deck-aistack-codes/decks/{deck_id}/editable-fields`
- `GET  /api/products/deck-aistack-codes/decks/{deck_id}/fields/{field_key:path}`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/changes/preview`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/changes/apply`
- `GET  /api/products/deck-aistack-codes/decks/{deck_id}/smart-deck`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/generation-jobs`
- `GET  /api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/generation-jobs/{job_id}`

### Exports
- `GET  /api/products/deck-aistack-codes/decks/{deck_id}/exports`
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/export`

### Due Diligence chat exact-once behavior

- `POST /api/products/deck-aistack-codes/decks/{deck_id}/due-diligence/chat` reserves provider execution by deck, user, audience, and `clientExchangeKey`.
- A completed duplicate replays its persisted response. A pending duplicate waits boundedly and then returns HTTP 409 with typed code `diligence_chat_pending`, `retryable: true`, and the same `clientExchangeKey`; it never invokes the provider again.
- Pending reservations are never automatically reclaimed or taken over. Crash recovery requires explicit operator reconciliation of the reservation and provider outcome rather than a duplicate provider call.
- Completion is conditional on the original ownership token and pending state, so a late or non-owner completion cannot overwrite the reservation.

### Design-version apply workflows

- `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/apply-design-version`
  remains the whole-deck apply command.
- `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/apply-slide-version`
  accepts one reviewed generated slide and durably composes it into a new active
  design version. Its strict request requires `candidateDesignVersionId`,
  `sourceSlideId`, `generatedSlideId`, `expectedCurrentDesignVersionId` (send
  explicit `null` when no active generated version exists), and
  `idempotencyKey`. The worker result publishes `activeDesignVersionId` and
  `activeSlideComposition`; entries without generated content use
  `compositionSource: source_fallback`. A stale pointer fails recoverably with
  `stale_active_design_version` and `reload_active_deck`.

### Non-goal
- No production logic should depend on frontend rewrite/proxy/canonical wrappers.
- No `/api/v1` route paths are part of this product runtime contract.
