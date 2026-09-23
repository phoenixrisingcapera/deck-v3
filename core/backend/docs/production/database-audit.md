# DeckAiStack production database audit

This document defines the production acceptance boundary for the DeckAiStack data layer.

## Databases and ownership

DeckAiStack must keep database ownership explicit:

- application database: users, workspaces, authentication sessions, billing, decks, slides, design versions, exports, provider settings and durable workflow state;
- vector capability: PostgreSQL with the `vector` extension, using the configured embedding dimension;
- training/export data: isolated from normal application reads and writes unless explicitly enabled.

No production service may silently fall back to SQLite or a placeholder connection string.

## Required audit coverage

The database audit must verify:

1. The resolved database dialect is PostgreSQL.
2. Alembic has one expected head and the connected database is at that revision.
3. Every SQLAlchemy model is represented in migration metadata.
4. Critical product tables exist for users, workspaces, authentication sessions, decks, slides, workflow jobs, workflow events, workflow artifacts and dependencies.
5. User/workspace ownership foreign keys and uniqueness constraints are present.
6. The `vector` extension exists and reports a version.
7. Every vector column uses the configured embedding dimension.
8. Required vector indexes use the same distance operator as application retrieval.
9. API and worker services use the same workflow database and can see the same durable jobs.
10. Worker leases, heartbeats, retries, stale recovery and terminal states are queryable.
11. Database references to storage artifacts resolve through the configured bucket provider.
12. Authentication sessions are committed before an access token is returned.

## Deployment rules

- Migrations have one owner: a Railway pre-deploy or migration service.
- API and worker services must fail closed when the schema is incompatible.
- Migration failures must never be converted into warnings followed by a healthy process.
- Detailed database diagnostics stay behind an admin boundary or deployment command. Public health responses remain minimal.

## Production commands

```bash
python -m alembic heads
python -m alembic current
python -m alembic upgrade heads
python scripts/audit_production_database.py
python scripts/verify_worker_database_wiring.py
pytest -q
```

## Railway service contract

All API and worker services must receive the intended shared values for:

- `DATABASE_URL`
- `AUTH_SECRET_KEY`
- workspace/provider encryption keys
- bucket endpoint, bucket name, access key and secret
- embedding provider, embedding model and embedding dimension
- Qwen/DashScope or other configured provider credentials

Dedicated `APP_ROLE=worker-*` services must share the application database with the API and claim only their configured workflow job type.

## Release acceptance

The release is blocked when any of the following is true:

- SQLite is active in production;
- Alembic reports multiple heads or a revision mismatch;
- `vector` is absent;
- vector dimensions do not match configuration;
- required tables, columns, constraints or indexes are missing;
- workers cannot claim and complete a durable test job;
- API and workers resolve different databases;
- auth sessions, billing state, deck state or workflow artifacts cannot be read after being committed.
