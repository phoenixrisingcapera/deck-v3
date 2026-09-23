# Smart Deck Stall Diagnosis

This note documents the current failure chain for the intake flow that shows:

- `Checking Smart Deck readiness`
- `Reading your uploaded slides`
- `Creating slide previews`
- `Preparing your Smart Deck workspace`

## What the frontend is doing

The browser is no longer supposed to manage the pipeline. It only polls the canonical workflow state and reacts to it.

Relevant frontend paths:

- `deck-frontend-rescue/src/lib/components/UploadDeck.svelte`
- `deck-frontend-rescue/src/routes/(app)/decks/[deckId]/processing/+page.svelte`
- `deck-frontend-rescue/src/lib/api/deckService/workflow.client.ts`

The loader now polls `GET /api/products/deck-aistack-codes/decks/{deckId}/workflow-state` and retries once if the workflow looks stale. It does not own job execution.

## What the backend is supposed to do

The canonical backend chain is:

1. Save the source deck
2. Queue source extraction
3. Read slides / extract source text
4. Render miniatures
5. Publish Smart Deck readiness
6. Allow the Smart Deck workspace to open

Relevant backend paths:

- `deck-backend-rescue/app/services/deck_workflow_service.py`
- `deck-backend-rescue/app/services/deck_processing_visibility_service.py`
- `deck-backend-rescue/app/services/smart_deck_readiness_service.py`
- `deck-backend-rescue/app/services/worker_runtime_status_service.py`
- `deck-backend-rescue/app/services/deployment_readiness_service.py`

The deck can only open when the workflow state reaches a ready phase such as:

- `smart_deck_ready`
- `preview_ready`
- `applied`
- `export_ready`

If that never happens, the UI will keep waiting.

## The likely failure boundary

When the loader is stuck on:

- `Reading your uploaded slides`
- `Creating slide previews`
- `Preparing your Smart Deck workspace`

the backend is usually stuck before the publish step. In practice that means one of these is failing:

- the source-extraction worker is not claiming jobs
- the worker heartbeat is stale
- a job is queued but never transitions to running/completed
- the deck has missing artifacts and the workflow remains degraded

The canonical workflow-state payload already exposes:

- `activeStage`
- `status`
- `nextAction`
- `canOpenSmartDeck`
- `canRetry`
- `degradedMode`
- `missingArtifacts`
- `failures`
- `workerHeartbeat`

## Admin endpoints to inspect

Use these first when a deck is stuck:

- `GET /api/admin/deployment-readiness`
- `GET /api/admin/decks/{deckId}/workflow-state`
- `GET /api/admin/workers/heartbeat`
- `GET /api/admin/decks/{deckId}/debug`
- `POST /api/admin/decks/{deckId}/retry-processing`
- `POST /api/admin/decks/{deckId}/requeue-stale-jobs`

These routes show whether the deck is blocked by:

- a stale worker heartbeat
- a queued job that no worker has claimed
- a failed or retryable workflow job
- missing preview artifacts

## Silent delete behavior

Old intake decks are now silently soft-deleted from the normal workspace list so they do not keep resurfacing as stale `Processing` rows.

Implemented in:

- `deck-backend-rescue/app/services/workspace_summary_service.py`

This is intentionally non-destructive:

- it sets `soft_deleted_at` metadata
- it does not hard-delete rows
- it keeps the explicit intake cleanup endpoint intact

## What still needs to work for the loader to finish

For the loader to reach `Open Smart Deck`, the backend must first publish a ready workflow state.

If it does not, the correct response is:

- retry the workflow from the processing page
- inspect the admin workflow-state route
- verify worker heartbeat freshness
- verify the source-extraction and preview-render jobs are actually being claimed

## Current diagnosis

The frontend is waiting on backend proof, not crashing.
The real problem is the worker pipeline not reliably advancing through source reading and preview rendering.

That means the fix boundary is backend orchestration, worker health, and workflow publication, not just UI polling.
