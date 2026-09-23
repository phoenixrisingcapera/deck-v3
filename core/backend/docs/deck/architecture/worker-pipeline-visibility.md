# Deck Worker Pipeline Visibility

## Purpose

This document records an older rescue implementation pass. The current durable
workflow implementation is now centered on `workflow_jobs`, `workflow_job_events`,
`workflow_job_artifacts`, and `workflow_job_dependencies`, with
`DeckExtractionRun` retained only as compatibility provenance for source
processing.

## Current deploy shape

```text
Deck frontend / Svelte app
  calls backend API

Deck backend / FastAPI repo
  app.main:app
  app/api/routes/deck_workflow.py
  app/services/deck_processing_worker_service.py
  app/services/workflow_job_service.py
  app/services/deck_processing_visibility_service.py
  scripts/deck_processing_worker.py

Railway API service
  runs: python scripts/start_railway.py with APP_ROLE=api

Railway worker service
  runs: python scripts/start_railway.py with APP_ROLE=worker and WORKER_KIND=<job family>
  public URL: none
```

## Pipeline model

```text
User uploads deck
↓
API saves DeckFile
↓
API creates durable workflow job rows
  source_ingestion -> source_extraction -> miniatures -> brand_extraction -> smart_deck_context -> db_publisher
↓
Worker claims durable workflow jobs by job_type
↓
Worker updates status/heartbeat/output on workflow_jobs
↓
Frontend/admin reads workflow-state and workflow-jobs
```

## Durable DB control fields

Stored on `workflow_jobs` and related tables:

```json
{
  "jobType": "source_extraction",
  "status": "running",
  "attemptCount": 1,
  "maxAttempts": 3,
  "lockedBy": "worker-host:1234",
  "heartbeatAt": "2026-06-22T12:00:05",
  "lockedUntil": "2026-06-22T12:15:05"
}
```

This gives the system the Archer/HPC-style checkpoint model: the database is the source of truth, not the bucket and not an invisible background process.

## API visibility endpoints

```text
GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state
GET /api/products/deck-aistack-codes/decks/{deck_id}/processing
```

`workflow-state` is canonical. `/processing` is a compatibility projection.

Visibility includes:

```text
upload.sourceSaved
processing.status
processing.stage
processing.stageLabel
processing.attemptCount
processing.lockedBy
outputs.slideCount
outputs.blockCount
outputs.assetCount
outputs.previewCount
nextAction
```

## Worker command

Local:

```bash
python scripts/deck_processing_worker.py
```

Railway worker service:

```text
Start Command: python scripts/deck_processing_worker.py
Public URL: none
```

Recommended worker env:

```env
APP_ROLE=worker
DECK_WORKER_POLL_INTERVAL_SECONDS=10
DECK_PROCESSING_MAX_ATTEMPTS=3
```

The worker also needs the same database and storage env values as the API service.

## What this rescue pass does not do

- Does not split into multiple Railway workers yet.
- Does not add Alembic columns for `stage`, `locked_by`, or `heartbeat_at`.
- Does not rewrite the frontend upload UI.
- Does not change Railway API deployment shape.

## Later production hardening

Once upload and Smart Deck work for testers, the next step is to add explicit DB columns:

```text
stage
attempt_count
max_attempts
locked_by
locked_at
heartbeat_at
```

That should be done through Alembic after the rescue deploy is stable.
