# Stuck Smart Deck Diagnosis

For the canonical Upload -> Smart Deck dependency graph, ownership map, and admin/debug checklist, see [`docs/refactor/mvp-backend-prune-map.md`](./refactor/mvp-backend-prune-map.md).

## What the user sees

The intake screen stays on:

- `Checking Smart Deck readiness`
- `Reading your uploaded slides`
- `Creating slide previews`
- `Preparing your Smart Deck workspace`

The message `Blocking reason: slides not read` is a backend readiness projection, not a frontend crash.

## What is actually happening

The frontend is polling backend workflow state correctly.

The blocker is that the workflow never reaches the source-read complete state that would let the readiness contract mark the deck openable.

## Live Railway evidence

Current Railway topology on July 2, 2026 shows:

- `deck-backend-api`: online
- `deck-frontend-web`: online
- `worker-source-ingestion`: online
- `worker-source-extraction`: online
- `worker-miniatures`: online
- `worker-smart-deck-context`: online
- `worker-db-publisher`: online
- `worker-brand-extraction`: online
- `worker-preview-render`: online
- `worker-schema-validation`: online
- `worker-llm-generation`: online
- `worker-apply-version`: online
- `worker-export`: online
- `worker-stale-job-rescuer`: online
- `deck-processing-worker`: online but deploy failed
- `dddecks-backend`: online duplicate backend service

Deployment status checks also show:

- `worker-source-extraction`: `SUCCESS`
- `worker-miniatures`: `SUCCESS`
- `worker-smart-deck-context`: `SUCCESS`
- `worker-db-publisher`: `SUCCESS`
- `worker-brand-extraction`: `SUCCESS`
- `deck-processing-worker`: `FAILED`
- `dddecks-backend`: `FAILED`

The actual PDF-reading path is the `source_extraction` worker family. The preview and workspace stages are handled by `worker-miniatures`, `worker-smart-deck-context`, and `worker-db-publisher`.

Live endpoint checks on July 2, 2026 show two important facts:

- `GET https://api.deck.aistack.codes/api/products/deck-aistack-codes/decks/deck_d0927e77fa25c6b7/workflow-state` returns a clean `401 Authentication required`
- `GET https://api.deck.aistack.codes/api/admin/decks/deck_d0927e77fa25c6b7/debug` also returns `401 Authentication required`
- other decks still return `200 OK` on `workflow-state`, which means the backend worker pipeline is alive for authenticated/accessible decks

That means the currently blocked deck is not failing because the backend crashed on the route. The live blocker for that specific deck is auth/session or access scope, layered on top of the workflow-state contract.

The legacy `deck-processing-worker` service should be treated as recovery-only or retired from the primary pipeline. It is the most obvious disconnected legacy worker in production because it is still present, but its deploy is failed.

Railway was normalized to explicit worker kinds after this diagnosis was written:

- `worker-source-extraction` redeployed successfully and is the PDF-reading worker
- `worker-miniatures` redeployed successfully and is the slide-preview worker
- `worker-db-publisher` redeployed successfully and is the readiness publisher
- `deck-processing-worker` is recovery-only now and should not be treated as part of the primary source-reading lane
- the current live branch on `deck-backend-api` is already the merged mainline deployment, so the remaining live blocker is the processing lane, not an un-deployed backend branch

## Pipeline boundary for PDF reading

The PDF read/extract path is the backend source pipeline:

- `worker-source-ingestion`
- `worker-source-extraction`
- `worker-miniatures`
- `worker-preview-render`

`worker-source-extraction` is the service that should actually read the uploaded PDF/PPTX, persist slides, and make `workflow-state.source.slideCount` / `source.extractionReady` true.

If the deck stays on `Reading your uploaded slides`, the backend is not advancing through the `source_extraction` stage. If it then advances to `Creating slide previews` but never opens Smart Deck, the missing stage is usually `miniatures`, `smart_deck_context`, or `db_publisher`.

## Why the loader stalls

`workflow-state` only returns `canOpenSmartDeck=true` when the backend has enough source and preview evidence.

If slide extraction never completes, the readiness service reports:

- `currentStep = reading_uploaded_slides`
- `blockingReason = slides_not_read`

That is the state currently shown in the UI.

If the request itself returns `401`, the frontend should stop polling and route the user to sign-in instead of waiting for readiness evidence that can never arrive.

## Confirmed regression in the source-read worker

The source pipeline had a concrete worker fallback bug:

- `app/services/deck_processing_worker_service.py` tried to reconstruct a missing extraction run by ordering `DeckFile` on `uploaded_at` and a non-existent `created_at` column.
- When the job reached that fallback path, the worker raised `AttributeError: type object 'DeckFile' has no attribute 'created_at'` before it could read the deck.
- That failure matches the stall at `Reading your uploaded slides` because the worker crashes before slide rows are persisted.

The fix is to order by `DeckFile.uploaded_at` only in the fallback lookup path.

This matters because some queued jobs still reach `_processing_run(...)` without an attached extraction run, so the fallback path must be safe.

## New root cause found in the upload path

The latest backend patch uncovered a separate silent failure before the worker even starts:

- `create_first_deck_upload(...)` and `complete_deck_upload(...)` were catching `queue_source_extraction(...)` exceptions and only logging them.
- That leaves the deck saved in the database, but no workflow job is enqueued.
- The UI then keeps polling `workflow-state` forever because the backend never advances the pipeline.

That failure now becomes an explicit `failed` processing response plus a failure ticket, so the product no longer pretends the deck was queued when it was not.

The public `smart-deck-readiness` route has been removed from the product path. The frontend now reads canonical `workflow-state` directly, so Smart Deck readiness only has one user-facing contract.

## Recovery action taken

I normalized worker role inference so Railway service names can select the correct worker kind without brittle manual env setup.

The legacy `deck-processing-worker` service is now treated as recovery-only by default instead of trying to act like a general-purpose worker.

The frontend processing page now auto-retries stalled decks once when the deck has been sitting in a stalled queued/processing state long enough, so older decks can re-enter the canonical source pipeline without a manual click.

The upload-side Smart Deck loader also retries a stalled source pipeline once before it gives up, so the user does not have to discover the retry path manually just to move past `Reading your uploaded slides`.

The frontend now also normalizes the backend `blockingReason` field and treats these explicit read-path blockers as retryable once:

- `slides_not_read`
- `slide_previews_missing`
- `workspace_not_prepared`

That is the practical fix for the symptom where the deck stays on the slide-reading or preview-creation screen even though the backend has already exposed the blocker reason.

The stale deck rows in the intake list were also being held alive by a frontend reload cache window after the backend marked them soft-deleted. The intake screen now forces a fresh deck-list reload after cleanup so old processing decks disappear immediately instead of continuing to look active.

Live Railway logs also showed the legacy worker loop deadlocking while trying to write `worker_heartbeat` telemetry. That means a worker can appear deployed and still fail to advance the deck because the heartbeat insert itself aborts the process. The heartbeat path now retries transient lock failures instead of crashing the loop.

The current live worker status after env normalization is:

- `worker-source-extraction`: `SUCCESS`
- `worker-miniatures`: `SUCCESS`
- `worker-db-publisher`: `SUCCESS`
- `deck-processing-worker`: `QUEUED` recovery-only redeploy, not the primary worker

Public health snapshots now report the platform queue as idle:

- `GET /api/health/worker` => `{"status":"ok","workerRequired":false,"blocked":false,"queue":{"active":0,"queued":0}}`
- `GET /api/health/storage` => `{"status":"ok","provider":"s3","queue":{"active":0,"queued":0},"runtimeError":null}`

That means the backend is not globally stuck on a drained queue or storage failure. The remaining verification gap is the authenticated per-deck `workflow-state` / admin debug response for the specific deck id from the browser logs.

## Next checks

- confirm `worker-source-extraction` keeps claiming jobs on Railway
- inspect `/api/admin/decks/{deckId}/workflow-state` for the stuck deck
- inspect `/api/admin/workers/heartbeat`
- verify the extraction job writes slide rows and thumbnail artifacts
- verify `workflow-state.source.slideCount > 0` and `source.extractionReady=true`
- if the source stage is healthy but Smart Deck still does not open, check that `worker-miniatures`, `worker-smart-deck-context`, and `worker-db-publisher` are not stale or disconnected
