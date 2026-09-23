# Instant HTML Checkpoint Recovery Runbook

## Final security controls

- Recovery is provider-free and is limited to one known-successful raw checkpoint for the exact failed generation operation.
- Provider-bound recovery and every idempotent replay require the current generation `fullHtmlProviderBinding`, the same `providerBindingHash` on the provider attempt and recovery record, the exact provider-attempt `requestContextHash`, the compilation grounding hash, and the committed design/raw/sanitized-artifact lineage. Provider-bound PR #244 checkpoints encrypted with the legacy workspace key remain readable only after those gates pass and are rotated to the purpose-derived key before promotion commits.
- Publication repeats the current source revision and complete binding/lineage validation before changing deck, workflow, or operation publication state.
- Historical unbound recovery is an emergency exception, disabled by default with `INSTANT_HTML_LEGACY_RECOVERY_ENABLED=false` and `INSTANT_HTML_LEGACY_RECOVERY_TICKET_ID` blank. It requires an exact one-operation super-admin request, an approved UUID ticket matching the temporary deployment setting, immutable source/extraction/request/context proof (including exact historical audience), and the durable target-bound authorization audit.
- Both provider-bound and historical recovery require the exact audited OpenAI model, a known HTTP 200 result, a provider response ID, and the preserved checkpoint. Neither path permits provider/model downgrade or unknown provider outcome.
- Replay/publication reuses the canonical V2 manifest validator and rechecks contract/version identities, exact generated IDs/counts, requested-source coverage, complete fact/metric traceability, context hash, encrypted artifact hashes/sizes, and canceled cleanup ownership.
- Recovery never starts provider transport and never consumes a second product credit.
- Cost evidence records the preserved amount and explicit `costSource` with certainty (`exact`, `estimated`, or `unknown`). Input and output token values each carry their own source and certainty; unavailable usage is `null`, never an authoritative zero.

## Rollout gate

Before enabling any operator recovery:

1. Deploy the API and publisher worker from the same reviewed revision.
2. Confirm the focused recovery, hardening, storage, compiler, and provider-audit suites pass in the pinned environment without provider-facing transport.
3. Confirm `compileall`, `pip check`, and both core and AI Alembic head checks pass.
4. Inventory the target read-only. Verify all binding hashes, request-context hash, current source revision, checkpoint retention/crypto state, downstream workflow lineage, and cleanup ownership are present and exact.
5. Keep a provider-bound checkpoint ineligible if binding proof is absent. A historical checkpoint is eligible only through the separately reviewed emergency path and only when every independent persisted owner proves the exact source, audience, provider success, context, and target authorization contract.

## Operation

Use only the super-admin control-plane endpoint for the exact deck, operation, and generation job. A successful response must report `providerCallExecuted: false`, `productCreditReconsumed: false` in durable disposition evidence, and either a new recovered preview or an exact idempotent replay.

Do not invoke provider reconciliation or provider transport as part of checkpoint recovery.

For one approved historical operation only:

Accepted reason codes are exactly:

- `historical_checkpoint_recovery` — recovery of a verified historical checkpoint.
- `incident_data_recovery` — recovery performed under an approved incident process.
- `customer_authorized_recovery` — recovery explicitly authorized for the affected customer operation. Use this code for today's planned invocation.

1. Confirm the target and ticket through the privacy-safe read-only inventory; never print the ticket or raw checkpoint.
2. Set `INSTANT_HTML_LEGACY_RECOVERY_ENABLED=true` and set `INSTANT_HTML_LEGACY_RECOVERY_TICKET_ID` to that approved ticket, then deploy the reviewed API revision.
3. Invoke the exact recovery endpoint once with `allowLegacyUnboundContext: true`, reason `customer_authorized_recovery`, and the matching ticket. Do not retry blindly; inspect the sanitized failure code first.
4. Immediately set `INSTANT_HTML_LEGACY_RECOVERY_ENABLED=false`, clear `INSTANT_HTML_LEGACY_RECOVERY_TICKET_ID`, and redeploy even if recovery failed.
5. Verify the durable authorization/recovery audits and final publication state without reading or logging raw content.

## Rollback

1. Stop new recovery invocations and the preview publisher worker.
2. Roll back API and publisher worker together. The `20260807_0002_cleanup_xfer` successor permits downgrade only when every cleanup row is `completed`; actionable, unknown, and `canceled` rows all block downgrade so retained published artifacts cannot become cleanup candidates again. It only reverses its transferred audit rows and tasks, leaving the published cleanup-outbox schema revision intact.
3. Leave quarantined checkpoints and cleanup outbox records intact for the existing reconciler.
4. Do not manually mark a recovered operation published or alter binding metadata. If publication validation blocks, preserve the records and investigate read-only.

Rollback does not make a checkpoint with missing persisted proof eligible. Leave any such checkpoint blocked and keep the emergency deployment gate disabled with a blank ticket.
