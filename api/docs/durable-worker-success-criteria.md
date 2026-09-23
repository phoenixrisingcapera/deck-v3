# Durable worker success criteria

This PR is complete when the worker is not only present in code, but wired into the product flow end to end.

## Frontend success criteria

- After upload, the UI uses the returned `next_action` to show the Create Smart Deck action.
- When the user starts Smart Deck processing, the UI calls `POST /api/products/deck-aistack-codes/decks/{deck_id}/workflows/source-extraction`.
- The UI treats `worker_required: true` and `background_started: false` as normal durable-worker mode.
- The UI polls `GET /api/products/deck-aistack-codes/decks/{deck_id}/workflow-state` until `nextAction` is `open_smart_deck`.
- The UI only opens the Smart Deck workspace as ready when `nextAction` is `open_smart_deck`.
- If `nextAction` is `retry_or_manual_review`, the UI shows a clear failed/manual-review state and does not pretend the deck is ready.

## Backend success criteria

- The API start endpoint only enqueues processing work.
- The API start endpoint does not run extraction inside the API request process.
- The start response is typed by `SmartDeckProcessingStartResponse`.
- The processing visibility response is typed by `DeckProcessingVisibilityResponse`.
- The processing visibility payload includes upload status, worker run status, output counts, and `nextAction`.
- Final worker failure is surfaced through `requiresManualReview` and `finalFailureReason`.

## Worker success criteria

- A separate Railway worker service runs with `APP_ROLE=worker`.
- The worker claims queued processing runs.
- The worker processes the claimed run and persists slides, assets, and processing metadata.
- Stale running jobs are detected and re-queued.
- Jobs that exceed the configured max attempts move to `dead_letter`.
- The worker does not require user traffic to continue processing queued decks.

## Data contract hardening criteria

- `/workflows/source-extraction` has a stable typed response contract.
- `/workflow-state` has a stable typed response contract.
- Frontend state decisions rely on `next_action` from start and `nextAction` from processing visibility.
- `worker_required`, `background_started`, `requiresManualReview`, and `finalFailureReason` are part of the explicit product contract.
- Contract tests fail if the API route returns to in-request background processing.
- Contract tests fail if the processing visibility route loses the typed response model.

## Deployment success criteria

- API Railway service runs with normal API role.
- Worker Railway service runs from the same backend repo using the worker role.
- API and worker share the same production database and upload storage configuration.
- Upload to saved source file works before worker processing starts.
- Starting Smart Deck creates or reuses a queued processing run.
- Worker logs show claim and completion or manual-review transition.
