# Deck processing worker service

Smart Deck creation uses a durable backend queue. The API service can enqueue work, but a separate worker service must be running in production to claim and complete queued deck extraction jobs.

## When this worker is required

Deploy this worker when the product should turn uploaded decks into ready Smart Deck workspaces. Without it, `/processing` can report `worker_not_running` or `worker_stalled`, and the frontend will correctly stop polling instead of staying on the loader.

The intake cleanup endpoint does not require this worker. Cleanup is synchronous database metadata work. This worker is only for actual deck processing/extraction.

## Railway setup

Create a second Railway service from the same backend repository or Docker image as the API service.

Use the same dispatcher entrypoint as the API service:

```bash
python scripts/start_railway.py
```

Set these worker-specific variables:

```bash
APP_ROLE=worker
WORKER_KIND=source_extraction
RUN_MIGRATIONS_ON_STARTUP=false
RUN_WORKER_MIGRATIONS_ON_STARTUP=false
DECK_WORKER_POLL_INTERVAL_SECONDS=10
DECK_WORKER_HEARTBEAT_INTERVAL_SECONDS=30
DECK_WORKER_STALE_AFTER_SECONDS=900
```

The worker service must also receive the same required runtime variables as the API service:

- `DATABASE_URL`
- auth/secret values used by the app settings
- upload storage bucket variables
- AI provider credentials required for Smart Deck processing

## Startup behavior

`scripts/start_railway.py` is role-aware:

- default `APP_ROLE=api` starts the FastAPI API service
- `APP_ROLE=worker` starts `scripts/deck_processing_worker.py`

The worker script:

- claims queued `deck_processing_queue` runs
- processes them through the durable worker service
- records heartbeat telemetry
- recovers stale running jobs back to queued when safe
- final-fails jobs that exceed retry limits
- serves `/api/health` and `/health` so Railway health checks can succeed

## Health and readiness

The worker health endpoint returns a lightweight process-level response:

```bash
curl https://<worker-service>/api/health
```

Expected response shape:

```json
{
  "status": "ok",
  "role": "worker",
  "workerId": "...",
  "workerStatus": "idle",
  "lastClaimedRunId": null,
  "lastError": null
}
```

The API readiness checks use heartbeat telemetry to detect whether a worker is fresh, stale, or missing.

## Local smoke checks

Process at most one queued job and exit:

```bash
APP_ROLE=worker python scripts/deck_processing_worker.py --once
```

Run the worker loop locally:

```bash
APP_ROLE=worker python scripts/start_railway.py
```

Verify wiring tests:

```bash
DATABASE_URL=sqlite:// python -m pytest tests/test_railway_deploy_config.py -q
```

## Failure behavior

If no worker is running, processing visibility reports a worker-specific next action after the stale threshold. The frontend can then stop the loader and show a retry/degraded path.

If a worker claims a run but stops heartbeating, stale recovery moves eligible jobs back to queued. Once retry limits are exceeded, the run is marked for manual review instead of being retried forever.
