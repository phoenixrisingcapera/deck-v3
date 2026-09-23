# Railway Pre-deploy Failure Recovery

Railway can fail before startup with this deploy-stage message:

```text
Deploy > Pre deploy command
Pre-deploy command failed
```

For this backend, the pre-deploy command is usually a database migration command such as:

```bash
alembic upgrade head
```

## Why this can fail

Alembic imports `app.core.config` to read the database connection. Before this fix, importing settings in production validated the entire API runtime configuration, including auth signing, AI providers, CORS, storage, and scanner settings.

A migration command should only need a valid production database URL.

## Fix added

Alembic now forces this role before importing settings:

```text
APP_ROLE=migration
```

That role validates only the production database URL. Runtime checks still run when the deployed service starts as either:

```text
APP_ROLE=api
APP_ROLE=worker
```

This separates migration readiness from API and worker runtime readiness.

## Important Railway variable warning

Do not leave documentation placeholders as literal Railway values. Values such as these must be replaced with real generated values or Railway reference variables:

```text
AUTH_SECRET_KEY
AUTH_SECRET_KEY_ID
WORKSPACE_AI_FERNET_KEY
WORKSPACE_AI_FERNET_KEY_VERSION
RAILWAY_BUCKET_NAME
RAILWAY_BUCKET_REGION
RAILWAY_BUCKET_ACCESS_KEY
RAILWAY_BUCKET_SECRET_KEY
OPENROUTER_API_KEY
```

The runtime validator now reports placeholder-like values more clearly.

## Recommended Railway commands

If Railway has a UI-level pre-deploy command, keep it focused on migrations:

```bash
alembic upgrade head
```

The repo start command remains:

```bash
python scripts/start_railway.py
```

## Verification

Run the migration with production-like environment values, then deploy the API with:

```text
APP_ROLE=api
```
