# Codex Prompt: Local Repository Guardrail Verifier

Goal: Create a local verifier that checks buildability, API boundary, secrets, and architecture drift.


Important rules:
- Do not move backend logic into the frontend.
- Do not expose secrets.
- Do not use /api/v1 for DidiDecks.
- DidiDecks APIs use /api/products/dididecks/*.
- Do not copy legacy Michael repo code.
- Run build/typecheck and report results.


Create:

- `lib/guardrails/dididecksArchitecture.ts`
- `scripts/verify-dididecks-repo.mjs`
- package script: `verify:repo`
- `product-status/repository-verification.md`

Verifier must check:

- build script exists
- typecheck script exists or fallback noted
- routes match expected DidiDecks route model
- concepts exist in types/data/API
- no `/api/v1` DidiDecks usage
- no frontend secrets
- editor is not disconnected from persistent fields
- map/smart-edit/rebuild API helpers exist or drift is reported

Readiness status:

- NOT_READY: critical/blocker/build/typecheck fail
- PARTIAL: architecture drift or warnings remain
- READY: no blockers, warnings, or drift
