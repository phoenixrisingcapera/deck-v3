# Bitácora — Worker Pipeline Visibility Port

Date: 2026-06-22
Repo: `phoenixrisingcapera/deck-Aistack-backend-new`
Branch: `port-worker-pipeline-visibility`

## /plan

Use the old Railway-backed FastAPI repo as the production recovery target. Do not rebase the monorepo into it. Port only the backend pieces needed to make Deck processing visible and worker-controlled.

Target behaviour:

```text
upload deck
→ queue DeckExtractionRun
→ worker claims queued run
→ worker writes stage metadata
→ visibility endpoint reports exact state
→ frontend/admin can show progress instead of generic failure
```

## /execute

Added:

```text
app/workers/__init__.py
app/workers/deck_queue_worker.py
app/services/deck_processing_visibility_service.py
docs/deck/architecture/worker-pipeline-visibility.md
```

Updated:

```text
app/services/deck_processing_queue_service.py
app/api/routes/deck_intake.py
```

New endpoint:

```text
GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state
GET /api/products/deck-aistack-codes/decks/{deck_id}/processing  # compatibility
```

New worker command:

```bash
python3 -m app.workers.deck_queue_worker
```

## /review

What this gives:

- One backend worker entrypoint for Railway.
- DB-controlled worker/job status through durable workflow rows.
- Canonical workflow visibility through `workflow-state`.
- A compatibility `/processing` endpoint for older consumers.

What remains:

- Test compile locally or in Railway preview.
- Add frontend polling if using the old frontend repo.
- Add an admin table later.
- Add explicit Alembic columns later after the rescue deploy is stable.
