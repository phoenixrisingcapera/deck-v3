# Frontend/backend deployment contract

## Backend base URL for production

Frontend should resolve the backend origin from the frontend source-of-truth env:

- `DECK_AISTACK_BACKEND_URL=https://api.deck.aistack.codes`

## Routing rule

- Server-side frontend routes should use `src/lib/server/backendUrl.ts` and the
  `DECK_AISTACK_BACKEND_URL` env var.
- Browser code should call the SvelteKit `/api` routes, not a separate browser-direct
  backend origin.
- Avoid hidden frontend proxy/rewrite dependency for core paths such as:
  - `/api/products/deck-aistack-codes/welcome-state`
  - `/api/products/deck-aistack-codes/workspace-summary`
  - `/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck`
- Any rewrite layer, if present, should be treated as temporary compatibility
  only and not required for production route validity.
