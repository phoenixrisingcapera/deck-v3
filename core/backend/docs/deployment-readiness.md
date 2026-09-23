# Deployment readiness checks

This check verifies the runtime pieces required for DeckAiStack production deployment.

## Admin endpoint

```text
GET /api/admin/deployment-readiness
```

Requires super admin access.

The endpoint reports:

- database reachability
- required production configuration
- storage pipeline health
- configured AI provider
- CORS origin health
- worker queue readability
- latest durable worker heartbeat

## Upload smoke test endpoint

```text
POST /api/admin/railway-upload-smoke-test?cleanup=true
```

Runs a backend-only synthetic deck upload through the persistence path and returns
readiness acceptance flags. Use it with a super-admin token from the same
environment you test deployment readiness in.

```bash
curl -X POST "http://localhost:8000/api/admin/railway-upload-smoke-test?cleanup=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Smoke script

Run inside the backend service container or Railway shell:

```bash
python scripts/smoke_deployment_readiness.py
```

The script exits with code 0 only when the hard readiness checks pass.

## Worker heartbeat

The durable worker records heartbeat telemetry while running. The API uses the latest heartbeat to show whether the worker is fresh, stale, or missing.

Useful variables:

```bash
DECK_WORKER_HEARTBEAT_INTERVAL_SECONDS=30
DECK_WORKER_HEARTBEAT_TTL_SECONDS=180
```

## Production-ready criteria

- API is deployed and healthy.
- Postgres connection succeeds.
- Storage write/read/signed-url checks succeed.
- Worker queue table is readable.
- Durable worker has a fresh heartbeat.
- At least one AI provider is configured.
- Frontend production origin is included in CORS.
