# Deck AI Stack Backend

See [Vision Deck Load Implementation](./docs/VISION_DECK_LOAD_IMPLEMENTATION.md)
for concurrent miniature rendering, Qwen vision transport, artifact ownership,
and production verification requirements.

Backend API and worker runtime for the product application.

## Runtime

- app entrypoint: `app.main:app`
- local API: `uvicorn app.main:app --reload --port 8080`
- Railway start command: `python scripts/start_railway.py`
- tests: `pytest`

## Documentation

Project documentation has been centralized outside this repo.

See:

- [documentation/README.md](/home/phoenix/Documents/andrea-projects-workspace/rescue-DECK/documentation/README.md)
- [documentation/backend/](/home/phoenix/Documents/andrea-projects-workspace/rescue-DECK/documentation/backend)
- [documentation/platform/](/home/phoenix/Documents/andrea-projects-workspace/rescue-DECK/documentation/platform)

## Remaining Markdown In This Repo

The markdown that still remains here is runtime-coupled and was left in place intentionally:

- `AGENTS.md`
- knowledge-pack content under `llm_knowledge/`
- prompt-package content under `app/llm/prompt_packages/`
- Terminal workflow outcomes are durable and queryable as `completed`,
  `failed_final`, `blocked`, and `timed_out`.

Dedicated worker entrypoints now available under `app/workers/`:

- `source_ingestion_worker.py`
- `source_extraction_worker.py`
- `miniatures_worker.py`
- `brand_extraction_worker.py`
- `smart_deck_context_worker.py`
- `db_publisher_worker.py`
- `llm_generation_worker.py`
- `schema_validation_worker.py`
- `preview_render_worker.py`
- `apply_version_worker.py`
- `export_worker.py`
- `stale_job_rescuer_worker.py`

Each entrypoint sets `DECK_WORKER_JOB_TYPES` for one job type and then runs the
shared queue loop. This allows deployment to run separate worker processes by
responsibility while still using one durable `workflow_jobs` claim/recovery
implementation.

The Railway/manual worker bootstrap scripts now also run the durable
`workflow_jobs` loop and honor `DECK_WORKER_JOB_TYPES`, so deployment can keep a
health-check wrapper while still claiming only the intended job types.

Deployment can now select dedicated workers by `APP_ROLE` as well:

- `worker-source-ingestion`
- `worker-source-extraction`
- `worker-miniatures`
- `worker-brand-extraction`
- `worker-smart-deck-context`
- `worker-db-publisher`
- `worker-llm-generation`
- `worker-schema-validation`
- `worker-preview-render`
- `worker-apply-version`
- `worker-export`
- `worker-stale-job-rescuer`

If one of those roles is used and `DECK_WORKER_JOB_TYPES` is unset, the worker
bootstrap maps the role to the matching job type automatically.
The rescuer role sets `DECK_WORKER_RECOVERY_ONLY=true` so it only runs stale
workflow-job recovery and never claims normal stage work.

Best-practice deployment rule:

- Production should run dedicated `worker-*` roles so each process claims one
  workflow `job_type`.
- The generic `worker` role remains a development or break-glass fallback, not
  the preferred production topology.

## Configuration

Copy `.env.example` to `.env` for local development. Production deployments must provide real values through the platform environment.

Required production settings include:

- `APP_ENV=production`
- `DATABASE_URL`
- `AUTH_SECRET_KEY`
- `AUTH_SECRET_KEY_ID`
- `WORKSPACE_AI_FERNET_KEY`
- `WORKSPACE_AI_FERNET_KEY_VERSION`
- `ALLOWED_ORIGINS` or `CORS_ORIGIN`
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`
- `UPLOAD_SECURITY_SCAN_COMMAND`

For durable production uploads, connect the backend service to the bucket using Railway's `AWS SDK (Generic)` connector. The backend accepts the AWS-style variables that connector injects, plus the older Railway aliases:

- `S3_BUCKET_NAME`, `AWS_S3_BUCKET_NAME`, `UPLOAD_STORAGE_S3_BUCKET`, or `RAILWAY_BUCKET_NAME`
- `AWS_DEFAULT_REGION`, `UPLOAD_STORAGE_S3_REGION`, or `RAILWAY_BUCKET_REGION`
- `AWS_ENDPOINT_URL`, `UPLOAD_STORAGE_S3_ENDPOINT`, or `RAILWAY_BUCKET_ENDPOINT`
- `AWS_ACCESS_KEY_ID`, `UPLOAD_STORAGE_S3_ACCESS_KEY`, or `RAILWAY_BUCKET_ACCESS_KEY`
- `AWS_SECRET_ACCESS_KEY`, `UPLOAD_STORAGE_S3_SECRET_KEY`, or `RAILWAY_BUCKET_SECRET_KEY`

If Railway injects `AWS_*` names through the bucket connector, that is the preferred path for this FastAPI/boto3 backend.

## Deck processing worker

Smart Deck extraction requires a separate long-running worker service in production.

Create a second Railway service from the same backend repository/image and set:

```bash
APP_ROLE=worker
RUN_MIGRATIONS_ON_STARTUP=false
RUN_WORKER_MIGRATIONS_ON_STARTUP=false
```

Use the same database, storage, auth, and AI provider environment values as the API service. The role-aware startup script runs `scripts/deck_processing_worker.py`, which claims queued deck-processing jobs, records worker heartbeat telemetry, recovers stale runs, and exposes `/api/health` for Railway health checks.

See `docs/deck-processing-worker-service.md` for the full deployment checklist.

## Public interest bot protection

Public interest bot protection is controlled separately from the public lead form:

- `TURNSTILE_SECRET_KEY` stores the Cloudflare Turnstile secret.
- `PUBLIC_INTEREST_TURNSTILE_REQUIRED=true` requires a browser token on `/api/public/interest`.
- Leave `PUBLIC_INTEREST_TURNSTILE_REQUIRED=false` until the frontend widget is configured, otherwise public lead submissions without a token will be blocked.

## Verification

```bash
python3 -m compileall -q app alembic scripts
```

```bash
DATABASE_URL=sqlite:// python scripts/verify_production_contract.py
```

```bash
python3 scripts/verify_admin_api_boundary.py
```

```bash
DATABASE_URL=sqlite:// python -m pytest tests/test_railway_deploy_config.py tests/test_tester_readiness_smoke.py tests/test_production_route_contract.py tests/test_public_interest_route.py -q
```

```bash
DATABASE_URL=sqlite:// python -m pytest tests/test_workspace_ai_provider_service.py tests/test_auth_route_security.py tests/test_smart_deck_route_security.py tests/test_deck_intake_route_security.py -q
```

Run migrations before deployment:

```bash
alembic upgrade head
```
