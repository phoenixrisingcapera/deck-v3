# Railway AI_DATABASE_URL Provisioning

## Overview

The science-backed pipeline requires an AI database with pgvector support. This document explains how to provision and configure the `AI_DATABASE_URL` environment variable on Railway.

## Architecture

The 2-database architecture uses:
- **Core DB** (`DATABASE_URL`): Product truth (users, decks, slides, blocks, billing)
- **AI DB** (`AI_DATABASE_URL`): AI/retrieval/training/evaluation (embeddings, LLM runs, training examples)

## Railway Provisioning Steps

### 1. Create AI Database Service

1. Go to Railway dashboard
2. Click "New Service" → "Database" → "PostgreSQL"
3. Name it `deck-ai-db` or similar
4. Enable the `pgvector` extension:
   - Go to the database service
   - Click "Data" tab
   - Run: `CREATE EXTENSION IF NOT EXISTS vector;`

### 2. Get Database URL

1. Go to the AI database service
2. Click "Variables" tab
3. Copy the `DATABASE_URL` value

### 3. Set Environment Variable

1. Go to the main backend service
2. Click "Variables" tab
3. Add new variable:
   - Name: `AI_DATABASE_URL`
   - Value: (paste the DATABASE_URL from step 2)

### 4. Run Migration

The migration creates 6 new tables in the AI database:

```bash
# Option 1: Run via Railway shell
railway shell
python scripts/run_science_backed_pipeline_migration.py

# Option 2: Run via Railway run
railway run python scripts/run_science_backed_pipeline_migration.py

# Option 3: Add to start command
# In railway.toml, add:
# [deploy]
# startCommand = "python scripts/run_science_backed_pipeline_migration.py && uvicorn app.main:app"
```

### 5. Verify Tables

Connect to the AI database and verify:

```sql
-- Check tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'artifact_objects',
    'materialized_deck_state', 
    'source_extraction_jobs',
    'llm_runs',
    'change_requests',
    'audit_log'
);
```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Core PostgreSQL URL | `postgresql://user:pass@host:5432/deck_core` |
| `AI_DATABASE_URL` | AI PostgreSQL URL with pgvector | `postgresql://user:pass@host:5432/deck_ai` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ROLE` | Application role (api/worker) | `api` |

## Fallback Behavior

When `AI_DATABASE_URL` is not set:
- The system falls back to using the core database for AI operations
- This is backward compatible but not recommended for production
- The `AI_DATABASE_ENV_ALIASES` in `app/core/railway_env.py` provides automatic detection

## Railway Alias Groups

The system automatically detects Railway database services:

```python
AI_DATABASE_ENV_ALIASES = (
    "AI_DATABASE_URL",
    "AI_DB_URL",
    "AI_POSTGRES_URL",
    "AI_POSTGRESQL_URL",
    "PGVECTOR_URL",
    "VECTOR_DB_URL",
)
```

## Migration Script

The migration script is located at:
```
scripts/run_science_backed_pipeline_migration.py
```

It:
1. Reads `DATABASE_URL` from environment or `alembic.ini`
2. Runs `alembic upgrade heads`
3. Verifies the migration

## Troubleshooting

### Migration fails with connection error

```bash
# Check if database is accessible
psql $AI_DATABASE_URL -c "SELECT 1;"

# Check if pgvector is installed
psql $AI_DATABASE_URL -c "SELECT * FROM pg_extension WHERE extname = 'vector';"
```

### Tables already exist

The migration is idempotent. If tables exist, it will skip creation.

### Permission denied

Ensure the database user has CREATE TABLE privileges:

```sql
-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE deck_ai TO your_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;
```

## Production Checklist

- [ ] AI database service created on Railway
- [ ] pgvector extension enabled
- [ ] `AI_DATABASE_URL` environment variable set
- [ ] Migration run successfully
- [ ] Tables verified in AI database
- [ ] Application restarted after migration
- [ ] Fallback behavior tested (AI DB down scenario)
