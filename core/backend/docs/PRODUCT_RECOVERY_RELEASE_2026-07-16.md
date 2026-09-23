# Product Recovery Release 2026-07-16

Tag: `v2026.07.16-production-reconciliation`

## Scope

This release stabilizes the two-database Railway runtime and the Qwen-backed
Smart Deck, Smart Edit, and Due Diligence contracts consumed by the canonical
frontend routes.

## Runtime Changes

- Keeps core product state in `DATABASE_URL` and vector/AI state in
  `AI_DATABASE_URL`, with separate Alembic ownership and topology checks.
- Adds forward-only core and AI reconciliation migrations.
- Makes Railway predeploy own both migration lineages and verifies database
  topology before application startup.
- Expands product readiness diagnostics for core DB, AI DB, pgvector, storage,
  migrations, and Qwen configuration.
- Hardens vector chunk synchronization, embedding metadata, content hashes,
  retrieval, and AI database contracts.
- Keeps production platform routing on Qwen while preserving explicit
  workspace BYOK boundaries.
- Adds Qwen vision and structured-output contract coverage.
- Preserves text-only Smart Edit backgrounds and records reviewable patches.
- Normalizes bounded Qwen render-schema formatting drift before applying the
  existing strict Pydantic schema.
- Increases default core and AI connection capacity from the exhausted `3+2`
  fallback to `5+5` while preserving environment overrides.
- Adds the Railway full-test report service and authenticated product smoke.

## Railway Diagnosis

Before this release, the deployed smoke passed health, authentication, upload,
source-slide persistence, and preview persistence, then failed Smart Deck
generation as `failed_retryable`.

The worker logs identified:

- layered render backgrounds without a top-level fill
- provider-only element `shape` and nested `style` fields
- overlong `analytics.slidePurpose`
- downstream schema and preview jobs missing `designVersionId`
- API pool exhaustion causing dashboard, graph, versions, workspace summary,
  provider settings, and failure-ticket requests to return 500

The release addresses the provider formatting drift and pool fallback. A fresh
deployed authenticated smoke remains the release gate.

## Verification

- Railway-aligned local suite: `93 passed, 6 skipped`.
- Focused Smart Deck render-schema suite: `7 passed`.
- Frontend/backend health endpoints were reachable during diagnosis.
- AI readiness reported Qwen `text-embedding-v3`, pgvector, and 1024 dimensions.
- `git diff --check`: passed.

## Deployment Gate

After both matching tags deploy:

1. Verify `/api/health`, `/api/health/ready`, and `/api/health/ai` return 200.
2. Run the Railway full-test runner with remote smoke enabled.
3. Require Smart Deck generation to persist a render schema and design version.
4. Require Smart Edit generation, reload, acceptance, and revision persistence.
5. Require Due Diligence run history to persist and reload.
