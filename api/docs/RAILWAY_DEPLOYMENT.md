# Railway Deployment Contract

This backend repo is intended to run as two separate Railway services from the same codebase:

1. `APP_ROLE=api` — FastAPI service for the DeckAiStack frontend.
2. `APP_ROLE=worker` — background deck-processing worker.

Both services use the same dispatcher entrypoint:

```bash
python scripts/start_railway.py
```

The dispatcher starts the correct process based on `APP_ROLE`.

## API service

Required runtime shape:

```text
APP_ROLE=api
APP_ENV=production
RAILWAY_ENVIRONMENT=production
DATABASE_URL=<Railway Postgres URL>
DECK_AISTACK_STORAGE_PROVIDER=s3
RAILWAY_BUCKET_NAME=<bucket name>
RAILWAY_BUCKET_REGION=<bucket region>
RAILWAY_BUCKET_ACCESS_KEY=<bucket access key>
RAILWAY_BUCKET_SECRET_KEY=<bucket secret key>
ALLOWED_ORIGINS=https://deck.aistack.codes
AUTH_SECRET_KEY=<32+ character secret>
AUTH_SECRET_KEY_ID=<active key id>
WORKSPACE_AI_FERNET_KEY=<valid Fernet key>
WORKSPACE_AI_FERNET_KEY_VERSION=<active version>
OPENROUTER_API_KEY=<or another production AI provider key>
```

The API service runs Alembic migrations before starting unless this is disabled:

```text
RUN_MIGRATIONS_ON_STARTUP=false
```

## Worker service

Required runtime shape:

```text
APP_ROLE=worker
APP_ENV=production
RAILWAY_ENVIRONMENT=production
DATABASE_URL=<same Railway Postgres URL>
DECK_AISTACK_STORAGE_PROVIDER=s3
RAILWAY_BUCKET_NAME=<bucket name>
RAILWAY_BUCKET_REGION=<bucket region>
RAILWAY_BUCKET_ACCESS_KEY=<bucket access key>
RAILWAY_BUCKET_SECRET_KEY=<bucket secret key>
DECK_WORKER_POLL_INTERVAL_SECONDS=10
```

By default, the worker does not run migrations. Let the API service own schema migration on deploy.

The dedicated Instant HTML renderer uses `railway.renderer.toml`, which intentionally
omits a pre-deploy command. It must never run or imply ownership of migrations; the
API service remains the sole schema-migration owner.

For role-specific job families, set `WORKER_KIND` on each dedicated worker service:

- `source_ingestion`
- `source_extraction`
- `miniatures`
- `brand_extraction`
- `smart_deck_context`
- `db_publisher`
- `llm_generation`
- `schema_validation`
- `preview_render`
- `apply_version`
- `export`
- `stale_job_rescuer`

## Product API contract

The frontend should call its own SvelteKit API proxies. Those proxies forward to backend routes under:

```text
/api/products/deck-aistack-codes/*
```

Critical routes:

```text
GET  /api/health
POST /api/auth/sign-in
GET  /api/auth/me
GET  /api/settings/workspace/ai-provider
GET  /api/products/deck-aistack-codes/workspace-summary
GET  /api/products/deck-aistack-codes/decks
POST /api/products/deck-aistack-codes/decks/upload
GET  /api/products/deck-aistack-codes/decks/{deck_id}/status
GET  /api/products/deck-aistack-codes/decks/{deck_id}/structure
GET  /api/products/deck-aistack-codes/decks/{deck_id}/smart-deck
```

Do not use `/api/v1` for DeckAiStack production traffic.

## Upload scanner note

The active upload route validates file type, MIME type, and size in Python before persistence. The Railway dispatcher sets `UPLOAD_SECURITY_SCAN_COMMAND=disabled` if the variable is absent so production boot is not blocked by an unused scanner setting.

Future scanner integration should be explicit: add the scanner call to the upload service first, then make the production setting mandatory again.

## Verification

Run before deployment:

```bash
python -m compileall -q app alembic scripts
DATABASE_URL=sqlite:// python scripts/verify_production_contract.py
```

## Pivotal branch and service lineage

`main` is the only canonical Railway deployment branch. Fix branches are
temporary review/publication branches; Railway services must follow the merged
`main` lineage rather than a long-lived worker branch.

| Branch | PR / merge | Status | Canonical areas | Railway services affected |
|---|---|---|---|---|
| `fix/open-backend-issues-mainline-20260818` | PR #266 / `72f5265` | merged into `main` | Microsoft connected-account exchange, worker startup preflight, workspace AI provider resilience, soft-delete contract | API and all durable worker roles |
| `fix/open-backend-issues-mainline-20260818` | PR #268 / `45f0003` | merged into `main` | S3-compatible upload-readiness normalization | API, renderer, and all durable worker roles sharing upload storage |
| `fix/worker-upload-readiness-v2-20260818` | PR #269 / `9794be7` | merged into `main` | worker-specific storage readiness separated from API upload-route requirements | all durable worker roles |
| `fix/worker-readiness-lineage-hardening-20260818` | PR #272 (follow-up to PR #269) | temporary publication branch; canonical only through its PR state and merged `main` lineage | capability-aware workspace encryption, S3/Supabase readiness validation, and this lineage record | all durable worker roles |
| `fix/website-brand-truthfulness-20260818` | PR #265 / `15bf562` | merged into `main` | website/deck palette provenance and brand readiness | API, source pipeline, brand extraction, Instant generation |
| `fix/instant-render-proof-selection-v2-20260818` | PR #264 / `78336ed` | merged into `main` | render proof and exact generated selection | API, preview worker, renderer |

Required post-merge checks:

1. Confirm remote `main` contains the merge commit.
2. Confirm each affected Railway role reports a terminal successful deployment
   from that `main` lineage with one running replica.
3. Confirm API uses `/api/health/product-ready`, renderer uses `/health/ready`,
   and workers use their coarse `/health` endpoint.
4. Record failed or superseded deployments separately from the currently
   serving successful deployment; a healthy old replica does not prove the new
   merge deployed.
5. Mark merged fix branches as historical/superseded. Never treat them as a
   second production source of truth.
