# Production workflow contract

This backend is the source of truth for the current DeckAiStack production product API.

The active production prefix is:

```text
/api/products/deck-aistack-codes
```

## Required workflow

The backend must support this production path:

1. Sign in / current user
2. Upload source deck
3. Persist deck/source file state
4. Return processing state
5. Return Smart Deck state only when ready or degraded
6. Return Brand Profile state
7. Return editable fields / change previews / change apply endpoints
8. Return exports
9. Expose Workspace AI Provider without blocking upload
10. Optionally support soft-delete and due-diligence surfaces

## Required backend routes

| Surface | Route |
|---|---|
| Health | `/api/health` |
| Sign in | `/api/auth/sign-in` |
| Current user | `/api/auth/me` |
| Workspace AI Provider | `/api/settings/workspace/ai-provider` |
| Workspace summary | `/api/products/deck-aistack-codes/workspace-summary` |
| Deck collection | `/api/products/deck-aistack-codes/decks` |
| Upload | `/api/products/deck-aistack-codes/decks/upload` |
| Status | `/api/products/deck-aistack-codes/decks/{deck_id}/status` |
| Workflow state | `/api/products/deck-aistack-codes/decks/{deck_id}/workflow-state` |
| Workflow job detail | `/api/workflow-jobs/{job_id}` |
| Source extraction workflow | `/api/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction` |
| Processing compatibility | `/api/products/deck-aistack-codes/decks/{deck_id}/processing` |
| Structure | `/api/products/deck-aistack-codes/decks/{deck_id}/structure` |
| Smart Deck | `/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck` |
| Brand Profile | `/api/products/deck-aistack-codes/decks/{deck_id}/brand-profile` |
| Editable Fields | `/api/products/deck-aistack-codes/decks/{deck_id}/editable-fields` |
| Change Preview | `/api/products/deck-aistack-codes/decks/{deck_id}/changes/preview` |
| Change Apply | `/api/products/deck-aistack-codes/decks/{deck_id}/changes/apply` |
| Exports | `/api/products/deck-aistack-codes/decks/{deck_id}/exports` |

## Optional staged routes

| Surface | Route |
|---|---|
| Soft Delete | `/api/products/deck-aistack-codes/decks/{deck_id}/soft-delete` |
| Due Diligence | `/api/products/deck-aistack-codes/decks/{deck_id}/due-diligence` |

## Rules

- Do not add DeckAiStack production routes under `/api/v1`.
- Do not switch this production repo to `/api/products/dididecks` unless frontend and backend migrate together.
- Workspace AI Provider failures must be diagnosed independently from upload failures.
- Smart Deck page load should be read-only from the frontend; processing starts from explicit action.
- `workflow-state` is the canonical state source for processing UI.
- `/processing` remains a compatibility projection over workflow state.

## Verification

`tests/test_production_workflow_contract.py` is intentionally a thin pytest
wrapper. The detailed checks live in
`scripts/verify_production_workflow_contract.py` so the same contract can be run
manually during local diagnosis and automatically in CI.

The workflow verifier checks:

- Required product routes are registered under `/api/products/deck-aistack-codes`.
- Legacy `/api/v1` and `/api/products/dididecks` route references are not used in production route code.
- Dedicated worker job types and worker entrypoints exist for the durable workflow pipeline.
- Pipeline DB models are present and exported.
- Required Alembic migrations and production schema repair migrations exist.
- Upload/storage artifact adapter exposes the required read/write/signed URL contract.
- `workflow-state` exposes the fields the frontend uses as canonical readiness truth.
- Human-readable workflow and deck-processing documentation exists.

Run:

```bash
DATABASE_URL=sqlite:// python scripts/verify_production_contract.py
DATABASE_URL=sqlite:// python scripts/verify_production_workflow_contract.py
DATABASE_URL=sqlite:// python -m pytest tests/test_production_workflow_contract.py -q
```
