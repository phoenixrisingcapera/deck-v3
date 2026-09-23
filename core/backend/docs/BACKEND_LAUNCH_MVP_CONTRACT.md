# Backend launch MVP contract

## Production goal

The backend `main` branch should deploy the working launch API to Railway:

- sign-in/sign-up/me routes are registered
- workspace AI provider route is registered
- bucket-backed upload/storage is configured
- deck upload/load/status routes are registered
- Smart Deck workspace route is registered under the product API prefix
- no production product route uses `/api/v1`
- no production deployment silently falls back to local file storage

## Production domains

- Frontend: `https://deck.aistack.codes`
- Backend API: `https://api.deck.aistack.codes`
- API prefix: `/api`
- Product prefix: `/api/products/deck-aistack-codes`

## Required Railway API service environment

```txt
APP_ENV=production
APP_ROLE=api
DATABASE_URL=<Railway Postgres URL>
AUTH_SECRET_KEY=<strong secret, at least 32 chars>
AUTH_SECRET_KEY_ID=<current key id>
WORKSPACE_AI_FERNET_KEY=<valid Fernet key>
WORKSPACE_AI_FERNET_KEY_VERSION=<current key version>
ALLOWED_ORIGINS=https://deck.aistack.codes
UPLOAD_STORAGE_BACKEND=s3
RAILWAY_BUCKET_NAME=<bucket name>
RAILWAY_BUCKET_REGION=<bucket region>
RAILWAY_BUCKET_ENDPOINT=<bucket endpoint if using Railway-compatible object storage>
RAILWAY_BUCKET_ACCESS_KEY=<bucket access key>
RAILWAY_BUCKET_SECRET_KEY=<bucket secret key>
DECK_GENERATION_MODE=openrouter
OPENROUTER_API_KEY=<provider key>
UPLOAD_SECURITY_SCAN_COMMAND=<configured scanner or safe production command>
```

## Required Railway worker service environment

```txt
APP_ENV=production
APP_ROLE=worker
DATABASE_URL=<same Railway Postgres URL>
UPLOAD_STORAGE_BACKEND=s3
RAILWAY_BUCKET_NAME=<same bucket name>
RAILWAY_BUCKET_REGION=<same bucket region>
RAILWAY_BUCKET_ENDPOINT=<same bucket endpoint>
RAILWAY_BUCKET_ACCESS_KEY=<same bucket access key>
RAILWAY_BUCKET_SECRET_KEY=<same bucket secret key>
DECK_GENERATION_MODE=openrouter
OPENROUTER_API_KEY=<same or worker provider key>
```

The worker service should run `python scripts/start_railway.py` with `APP_ROLE=worker` and a dedicated `WORKER_KIND`, and it should not use an HTTP healthcheck.

## Production safety rule

`UPLOAD_STORAGE_BACKEND=local` is not allowed in production.

The backend should fail fast if production storage is not `s3` or `supabase`, because the launch app must preserve uploaded decks, generated assets, Smart Deck artifacts, and export files in durable storage.

## Required launch routes

```txt
/api/health
/api/health/storage
/api/auth/sign-in
/api/auth/sign-up
/api/auth/me
/api/settings/workspace/ai-provider
/api/products/deck-aistack-codes/welcome-state
/api/products/deck-aistack-codes/workspace-summary
/api/products/deck-aistack-codes/decks
/api/products/deck-aistack-codes/decks/upload
/api/products/deck-aistack-codes/decks/{deck_id}/status
/api/products/deck-aistack-codes/decks/{deck_id}/structure
/api/products/deck-aistack-codes/decks/{deck_id}/editable-fields
/api/products/deck-aistack-codes/decks/{deck_id}/changes/preview
/api/products/deck-aistack-codes/decks/{deck_id}/changes/apply
/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck
/api/products/deck-aistack-codes/decks/{deck_id}/smart-deck/generation-jobs
```

## Verification before merge

Run from backend root:

```bash
python -m compileall -q app alembic scripts
DATABASE_URL=sqlite:// python scripts/verify_production_contract.py
DATABASE_URL=sqlite:// python -m pytest tests/test_production_route_contract.py tests/test_railway_deploy_config.py tests/test_tester_readiness_smoke.py -q
DATABASE_URL=sqlite:// python -m pytest tests/test_workspace_ai_provider_service.py tests/test_auth_route_security.py tests/test_smart_deck_route_security.py tests/test_deck_intake_route_security.py -q
```
