# Fetch logging production boundary

## Purpose

Browser fetch debugging belongs to the frontend only and must be disabled in production unless explicitly enabled for diagnosis.

The backend must not contain browser `window.fetch` wrappers, browser console fetch diagnostics, or production route changes for frontend-only logging.

## Backend rule

Backend production readiness stays focused on API contracts, request IDs, and route-level observability. It should not emit strings such as:

- `Fetch finished loading:`
- `Fetch failed loading:`
- `window.fetch`

## Verification

Run:

```bash
python scripts/verify_fetch_logging_contract.py
DATABASE_URL=sqlite:// python -m pytest tests/test_fetch_logging_contract.py -q
python -m compileall -q app alembic scripts
```

## Railway verification

```bash
curl -i "$BACKEND_URL/api/health"
curl -i "$BACKEND_URL/api/products/deck-aistack-codes/workspace-summary"
curl -i "$BACKEND_URL/api/products/deck-aistack-codes/decks"
```

Expected result:

- Backend routes still respond normally.
- Backend logs should use server-side request/error observability, not browser fetch debug messages.
