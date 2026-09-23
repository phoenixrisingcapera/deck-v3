# Database Alignment Release - 2026-07-17

## Release Scope

Backend commit `46c96936cbb41d8dc028eaa3db7fc4d8475eb290` advances the
database and runtime alignment plan across these canonical contracts:

- guarded recovery for historical `dependency_output_missing` workflow jobs;
- workspace Qwen model-category persistence and runtime resolution;
- provider-capacity error normalization and optional configured fallback;
- workspace-aware embedding and retrieval contracts;
- source-grounded brand design-token mapping;
- durable provider failure details for operator diagnosis.

The root execution plan remains `DB_ALIGNMENT_EXECUTION_PLAN.md` in the shared
workspace. This repository document records the deployable backend release.

## Historical Workflow Recovery

Canonical endpoint:

```text
POST /api/admin/decks/{deck_id}/jobs/{job_id}/recover-dependency-output
```

The endpoint is restricted to `super_admin` and only considers jobs that are:

- `blocked`;
- `schema_validation` or `preview_render`;
- blocked with `dependency_output_missing`.

Recovery requires all dependency edges to be present, completed, and owned by
the same deck. Exactly one required upstream stage must expose a persisted
same-deck `designVersionId`. An equivalent queued, retryable, or running job
prevents requeue.

The service locks the deck, target job, dependencies, and equivalent active
jobs before transition. The queued workflow transition, workflow event, and
security audit commit atomically. Ineligible jobs remain blocked and return a
precise manual-review reason.

## Verification

Focused local contracts cover:

- safe schema-validation recovery;
- safe preview-render recovery;
- missing or incomplete dependency output;
- missing and cross-deck design versions;
- cross-deck and ambiguous upstream jobs;
- equivalent active-job rejection;
- super-admin authorization;
- workflow-event and security-audit persistence;
- rollback when audit persistence fails;
- production route registration and frontend-worker boundaries.

Release verification commands:

```bash
python3 -m pytest \
  tests/test_admin_deck_repair_contract.py \
  tests/test_admin_processing_observability_contract.py \
  tests/test_generation_dependency_output_contract.py \
  tests/test_production_route_contract.py \
  tests/test_production_workflow_contract.py \
  tests/test_workflow_frontend_worker_boundary.py -q

git diff --check
python3 scripts/verify_database_topology.py
```

Railway acceptance remains incomplete until the API and full-test runner are on
the tagged commit and the full report reaches a terminal green state.

## Operational Guardrails

- Inventory eligible historical jobs read-only before invoking recovery.
- Use `python3 scripts/inventory_dependency_output_jobs.py` for the redacted
  aggregate inventory. It returns counts by job type and eligibility reason;
  it never prints deck/job/workspace/user identifiers or payloads.
- Do not bulk-requeue jobs or bypass the guarded endpoint.
- Do not recover a job when its upstream output or design-version ownership is
  ambiguous.
- Do not delete legacy Core tables without a fresh inventory, backup, owner,
  and explicit retention decision.
- Do not record credentials or environment values in release evidence.

## Remaining Gates

1. Deploy the tagged backend commit to the API and full-test runner.
2. Verify exact Core and AI migration heads and physical topology.
3. Run the Railway full-test report through generation, schema validation,
   preview rendering, apply-version, Smart Edit, Due Diligence, and export.
4. Record a read-only inventory of historical recovery candidates and extra
   Core tables before any production mutation.
5. Complete account-owner secret rotation and post-rotation health checks.
