# Postgres Runtime Schema Repair

Railway Postgres logs showed the backend database schema was behind the ORM model.

Observed missing runtime objects:

```text
column decks.current_design_version_id does not exist
relation failure_tickets does not exist
relation rate_limit_buckets does not exist
column security_audit_events.request_id does not exist
```

This is not a Postgres service failure. It is application schema drift.

## Repair added

`scripts/ensure_runtime_schema.py` is an idempotent bootstrap script. It patches only the runtime objects observed missing in production logs:

- `decks.current_design_version_id`
- `security_audit_events.request_id`
- `rate_limit_buckets`
- `failure_tickets`
- supporting indexes

The script forces `APP_ROLE=migration` internally so it only validates the production database URL before applying the patch.

## Railway configuration

`railway.toml` now includes:

```toml
[deploy]
preDeployCommand = "python scripts/ensure_runtime_schema.py"
startCommand = "python scripts/start_railway.py"
```

This makes schema repair happen before the API starts.

## Manual command

You can also run this from the Railway service shell:

```bash
python scripts/ensure_runtime_schema.py
```

## After repair

Redeploy the API service from `main` and confirm these errors stop appearing in Postgres logs.
