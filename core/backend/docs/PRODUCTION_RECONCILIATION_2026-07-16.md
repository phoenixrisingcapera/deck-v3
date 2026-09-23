# Production Reconciliation - 2026-07-16

## Release Status

The canonical Railway upload-to-export workflow passed in production on
2026-07-16. The passing run used isolated test data and exercised the mounted
product API rather than compatibility or concept routes.

Release tag: `v2026.07.16-production-reconciliation`

## Database Contract

- Core database head: `20260715_0005_core_data_contract_reconciliation`
- AI database head: `0003_ai_contract_hardening`
- Core version table: `alembic_version_core`
- AI version table: `alembic_version_ai`
- Core and AI resolve to separate PostgreSQL database identities.
- Core contains no AI-owned tables.
- AI contains no Core-owned tables.
- AI pgvector version: `0.8.5`
- Stored embedding type: `vector(1024)`
- Vector indexes were present on `vector_chunks`.

Railway predeploy runs the Core and AI migration lineages in sequence, then
runs the read-only topology verifier. SQLAlchemy inspection transactions are
committed before Alembic starts so migration DDL and version stamps persist.

## Production Deployments

- API: `193c5e50-792f-42a4-86c9-e33c82a695ee`
- Worker: `23dad5cc-3738-49c3-a8f8-b82189873fc8`
- Full-test runner: `1283a6a0-0939-423f-ba5a-69b9f7d72401`

`GET /api/health/product-ready` returned `ready` for Core, AI, storage, and
Qwen after deployment.

## Acceptance Evidence

The full-test report completed with `10` passed, `0` failed, and `0` blocked:

1. Local contract suite: `99 passed`
2. Deployed frontend and backend health
3. Deployed isolated-user authentication
4. PDF upload, four persisted source slides, and authenticated miniature
5. Real Qwen Smart Deck generation with persisted render-schema JSON
6. Generated design-version acceptance and apply
7. Smart Edit generation, reload, acceptance, and revision persistence
8. Due Diligence execution and reloadable history
9. Final-deck export persistence for admin release
10. Complete canonical deployed product smoke

The uninterrupted deployed product smoke took `526568 ms`.

## Runtime Repairs

- Production Qwen routing ignores stale Claude/OpenRouter workspace and request
  model selections.
- Smart Deck generation uses the configured Qwen timeout.
- The canonical `RenderSchema` JSON Schema is included in generation context.
- Invalid Qwen render schemas receive one explicit repair pass and are then
  revalidated strictly.
- Vision-backed prompts no longer duplicate base64 images in both text context
  and multimodal attachments.
- Smart Deck message creation no longer masks provider failures with a
  generation-job foreign-key failure.
- Deterministic deck analysis now constructs `BlockClassification` from its
  current block-owned ORM contract.
- The full-test runner uses canonical product endpoints, waits through eligible
  durable-job retries, and verifies apply and export persistence.

## Residual Follow-Up

- The broader legacy test suite contains older contract assumptions outside the
  release runner's passing acceptance set.
- Orphan-vector and publication hash reconciliation remain follow-up work.
- Legacy AI orchestration session ownership still warrants a dedicated audit.
- Export download remains intentionally gated by admin release policy.
