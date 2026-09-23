# Railway deployment contract

## Service split

- API service should run only the FastAPI app.
- Worker service should run deck-processing worker code.
- Worker service must not be used to answer HTTP routes.

## API service

- `APP_ROLE=api`
- `startCommand`: `python scripts/start_railway.py`
- `healthcheckPath`: `/api/health`
- Shared data/env: same `DATABASE_URL`, same storage credentials, same production safety variables.

## Worker service

- `APP_ROLE=worker`
- `WORKER_KIND=<job family>`
- `startCommand`: `python scripts/start_railway.py`
- `startCommand` dispatches to `scripts/deck_processing_worker.py` for worker roles.
- No HTTP healthcheck path for worker-only service.
- Shared data/env: same `DATABASE_URL`, same storage credentials, same production safety variables.
