---
title: Main consolidation handoff
date: 2026-07-03
repo: deck-Aistack-backend-new
branch: main
tags:
  - deckaistack
  - workflow-state
  - worker-runtime
  - runtime-schema
  - production-consolidation
  - railway
  - observability
status: merged-to-main
---

# Main Consolidation Handoff

This document records the backend side of the July 3, 2026 production
consolidation merge. It is the operational reference for the Upload -> Smart
Deck path after the merge.

## References

- Main merge commit: `a1c61b0 merge: consolidate workflow backend hardening`
- Source work commit: `f6c3d68 chore: consolidate workflow runtime hardening`
- Runtime schema fix: `68ba182 fix: repair smart deck generation runtime schema`
- Frontend companion merge: `dee294d merge: consolidate smart deck frontend refactor`
- Admin companion docs: `13e9ce1 docs: add observability debug traces`

## Contract Boundary

The backend owns deck readiness. Frontend and admin consumers should read:

```txt
GET /api/products/deck-aistack-codes/decks/{deckId}/workflow-state
```

The response must be the source of truth for:

- `status`
- `activeStage`
- `nextAction`
- `canOpenSmartDeck`
- `canRetry`
- missing artifacts
- worker/job failures
- degraded mode

## Files To Inspect First

- `app/api/routes/deck_workflow.py`
- `app/services/deck_workflow_service.py`
- `app/services/workflow_job_service.py`
- `app/services/runtime_schema_service.py`
- `app/services/deck_structure_service.py`
- `app/services/worker_runtime_status_service.py`
- `scripts/start_railway.py`
- `scripts/ensure_runtime_schema.py`
- `tests/test_runtime_schema_service.py`
- `tests/test_worker_service_name_normalization.py`
- `tests/test_railway_deploy_config.py`

## Verified

- `python3 -m compileall -q app scripts alembic`
- `PYTHONPATH=/tmp/deck-backend-main DATABASE_URL=sqlite:// ... pytest tests/test_runtime_schema_service.py tests/test_worker_service_name_normalization.py tests/test_railway_deploy_config.py -q`
- `PYTHONPATH=. DATABASE_URL=sqlite:// ... scripts/verify_production_contract.py`

Result:

```txt
11 passed
Production contract checks PASSED
```

## Known Gaps

- Live Railway still needs deployment confirmation after the pushed merge. A
  successful GitHub push is not proof that every service has rolled forward.
- Runtime schema repair is now part of the backend code path, but production
  should still be checked for existing schema drift before retrying stuck decks.
- The legacy `deck-processing-worker` should remain outside the active
  processing path. If it is kept, it must stay recovery-only and must not claim
  normal source extraction, miniatures, brand, or publish jobs.
- Failure tickets should be expanded so every terminal worker failure has an
  admin-visible ticket with deck id, job type, attempt count, and storage keys.

## Follow-Up Tasks

- Confirm Railway service heads match backend `main` commit `a1c61b0`.
- Re-read workflow-state for a known stuck deck after `worker-source-extraction`
  redeploys.
- Add a smoke command that creates a source ingestion job and verifies exactly
  one worker kind can claim it.
- Add a database schema audit endpoint for the admin console so missing runtime
  tables/columns are visible before they break workers.
