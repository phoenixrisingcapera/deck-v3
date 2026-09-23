# Backend canonical production contract

This backend repo is the current DeckAiStack production backend. It is not the monorepo refactor target.

## Product API prefix

The production product API family is:

```text
/api/products/deck-aistack-codes/*
```

Do not introduce DidiDecks production routes under `/api/v1`.

## Registered production anchors

The backend must keep these route families registered:

- `/api/health`
- `/api/auth/*`
- `/api/settings/workspace/ai-provider`
- `/api/products/deck-aistack-codes/welcome-state`
- `/api/products/deck-aistack-codes/workspace-summary`
- `/api/products/deck-aistack-codes/decks`
- `/api/products/deck-aistack-codes/decks/upload`
- `/api/products/deck-aistack-codes/decks/{deck_id}/status`
- `/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state`
- `/api/workflow-jobs/{job_id}`
- `/api/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction`
- `/api/products/deck-aistack-codes/decks/{deck_id}/processing` as a compatibility projection
- `/api/products/deck-aistack-codes/decks/{deck_id}/structure`
- `/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck`
- `/api/products/deck-aistack-codes/decks/{deck_id}/editable-fields`
- `/api/products/deck-aistack-codes/decks/{deck_id}/changes/preview`
- `/api/products/deck-aistack-codes/decks/{deck_id}/changes/apply`
- `/api/products/deck-aistack-codes/decks/{deck_id}/exports`

## Frontend/backend boundary

Backend docs may reference frontend routes only as consumer URLs. Backend code must not import frontend code or claim ownership of Svelte components.

Frontend-only component names such as upload widgets, save-confirmation banners, or Svelte route-group paths belong in the frontend repo.

## Railway runtime boundary

The API and worker are separate runtime roles:

- `APP_ROLE=api` starts the FastAPI API service.
- `APP_ROLE=worker` starts the durable workflow worker loop.
- `APP_ROLE=worker-*` scopes one process to one workflow `job_type`.

Do not create a second worker just to resolve canonical docs drift.

## Verification

Run:

```bash
DATABASE_URL=sqlite:// python scripts/verify_production_contract.py
python scripts/verify_canonical_backend_contract.py
```
