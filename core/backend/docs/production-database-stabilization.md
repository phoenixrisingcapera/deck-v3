# Production Database Stabilization

## Ownership

The production architecture has two PostgreSQL services:

| Service | Variable | Owns |
| --- | --- | --- |
| `deck-primary-db` | `DATABASE_URL` | Auth, users, workspaces, billing, decks, files, slides, workflows, exports, audit |
| `Postgres` | `AI_DATABASE_URL` | Vectors, embeddings, AI runs, telemetry, retrieval traces, regression cases, learning memories, AI dead letters |

`deck-user-db` was removed after `AI_DATABASE_URL` was switched to the dedicated AI service. No third product database is required.

## Migration Lineages

- Core: `alembic/`, target metadata `CoreBase`, command `python scripts/run_database_migrations.py core`.
- AI: `alembic_ai/`, target metadata `AiBase`, command `python scripts/run_database_migrations.py ai`.
- The core environment never runs against `AI_DATABASE_URL`.
- The AI baseline creates `vector` and uses `vector(1024)` only.
- Runtime `create_all()` and auth-session table creation are disabled. A failed migration blocks readiness instead of being repaired on the first request.

## Reconciliation Plan

1. Back up `deck-primary-db` before the first production migration.
2. Record tables in both databases with `SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename`.
3. Run the core migration job and verify `SELECT version_num FROM alembic_version` on the core database.
4. Run the AI migration job and verify the independent `alembic_version`, `vector` extension, and `vector_chunks.embedding` dimension.
5. If legacy AI tables exist in the core database, export them, copy only AI-owned rows into the AI database, validate counts and hashes, then remove them in a separately reviewed cleanup migration. The first forward migration does not drop data.

## Rollback

- Stop the worker before rollback.
- Keep the last known-good API deployment available.
- Restore the affected database from the pre-migration backup if a destructive reconciliation has begun.
- Use `alembic downgrade` only for a migration explicitly verified to be reversible. The AI baseline downgrade is intentionally a no-op to preserve production data.
- Restore the previous Railway variables only after confirming the target database and migration head.

## Readiness and Smoke Tests

```bash
curl -i https://api.deck.aistack.codes/api/health/live
curl -i https://api.deck.aistack.codes/api/health/ready
curl -i https://api.deck.aistack.codes/api/health/ai
curl -i https://api.deck.aistack.codes/api/health/worker
```

Expected: liveness `200`; readiness and AI readiness `200` only after their independent migration heads are present. A failed AI migration must return `503` from `/api/health/ai` without invalidating auth.

## Verification Completed

- `CoreBase.metadata.tables`: 71 product tables.
- `AiBase.metadata.tables`: 11 AI-only tables.
- Focused contract suite: 90 passed.
- Railway deployment `d3675c38-ea8c-4479-8a47-16b649774304`: SUCCESS.
- Railway `/api/health/live`: HTTP 200.
- Railway `/api/health/ready`: HTTP 200.
- Railway `/api/health/ai`: HTTP 200; DashScope `text-embedding-v3`; actual vector length 1024.
- Railway signup, signin, and `/api/auth/me`: HTTP 201/200/200.
- Railway upload and processing status: upload HTTP 200; processing HTTP 200.
- Railway market research: HTTP 200 with deck-scoped response.
- Railway Smart Edit preview: HTTP 200 with persisted change request.
- Railway Due Diligence run: HTTP 200.
- Core production AI table inventory: none after reconciliation.
- AI production inventory: independent vector, telemetry, run, embedding, retrieval, and dead-letter tables; 1,500,837 telemetry rows and 3 usage buckets preserved.

Railway verification must be rerun after both migration jobs complete and must include signup, signin, `/api/auth/me`, upload, processing, Smart Deck, Smart Edit, Due Diligence, market research, export, and the embedding probe.
