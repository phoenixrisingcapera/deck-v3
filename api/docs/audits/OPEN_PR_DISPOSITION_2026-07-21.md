# Backend Open PR Disposition — 2026-07-21

## Scope and safety

This is a read-only disposition of the 18 backend pull requests that remained
open after PR #106 merged. No pull request, branch, or source file was closed,
deleted, or merged during this audit. Each PR predates current `main` by 248 to
586 commits, and `git cherry origin/main <head>` found no patch-equivalent
commit for any PR. Old green checks therefore do not establish current release
fitness.

## Disposition

| PR | Disposition | Evidence and next action |
|---|---|---|
| #92 VC knowledge RAG foundation | Still relevant, re-scope | Maps to the current P2 RAG program, but adds a large endpoint/model/migration family from an old base. Re-evaluate against canonical Core/AI ownership and extract a fresh bounded PR; do not merge the historical branch. |
| #91 senior VC prompt engine | Deferred LLM scope | Fifty files of prompts and LLM runtime changes belong to typed prompt governance and the final LLM phase, not this non-LLM run. Reconcile packages against current loaders before any new PR. |
| #89 processing status/admin health | Superseded architecture | Current `workflow_state_read_model` is the readiness authority and current admin health services own diagnostics. Do not restore parallel product/admin route families. |
| #85 artifact bucket namespaces | Still relevant, re-scope | Artifact namespace requirements remain useful, but current shared storage and artifact services changed substantially. Audit current canonical storage selectors and extract only missing behavior with current tests. |
| #84 parallel Smart Deck architecture | Superseded documentation | Current root architecture and durable worker documents are newer and authoritative. Preserve as historical PR; do not merge stale architecture text. |
| #83 Smart Deck parallel orchestrator design | Superseded documentation | Current durable workflow/worker architecture supersedes this design-only PR. Preserve as history. |
| #81 runtime schema/upload hardening | Conflicting/unsafe | Runtime schema bootstrap conflicts with sole Alembic migration ownership; upload behavior has newer shared-storage repairs. Do not merge. Re-raise any reproduced defect against current migration/upload owners. |
| #74 deterministic brand palette | Still relevant, re-scope | Brand extraction remains active, but current services and contracts diverged. Compare behavior with current canonical brand extraction and port only a reproduced gap. |
| #72 brand source labels | Still relevant, re-scope | Source provenance remains useful. Verify whether current brand schemas already expose equivalent labels; otherwise create a fresh contract-first PR. |
| #70 processing observability | Superseded architecture | Uses the retired `deck_processing_visibility_service.py` owner. Current processing visibility plus workflow-state read model supersede it. |
| #69 workspace AI summary | Superseded by later provider work | Current workspace provider service, credential isolation, and OpenAI-default releases supersede this old service diff. |
| #67 Due Diligence route contract | Superseded by durable workflow | Canonical Due Diligence is now a durable backend-owned workflow. Do not merge the older route/main wiring. |
| #66 brand profile card contract | Superseded surface boundary | Brand persistence and mounted card contracts were delivered through later coordinated backend/frontend work. Reopen only for a reproduced current payload defect. |
| #64 provider soft-delete contract | Superseded by later provider work | Later provider boundary, fail-closed credential, readiness, and OpenAI-default changes supersede this PR. |
| #63 upload 503 readiness | Superseded and check-failing | Later PR #102 plus runtime proof repaired upload/previews. The historical check failed and the PR mixes workflow/config/docs/runtime files. |
| #30 Smart Deck retry recovery | Superseded and check-failing | Current durable workflow retry/read-model/admin recovery contracts supersede this route family. Do not restore a duplicate retry endpoint. |
| #25 market research knowledge runtime | Deferred LLM scope | Large LLM/knowledge endpoint family from a very old base. Reconcile under current durable deck-intelligence/RAG ownership during the final LLM program. |
| #17 Railway environment aliases | Conflicting/unsafe | Current environment contract intentionally uses canonical names and value-safe references; implicit aliases risk precedence drift. Historical check failed and includes a temporary file. Do not merge. |

## Summary

- Still relevant but requires a fresh bounded implementation: #92, #85, #74,
  #72.
- Deferred until LLM work is explicitly active: #91, #25.
- Superseded by current architecture or later merged work: #89, #84, #83,
  #70, #69, #67, #66, #64, #63, #30.
- Conflicting or unsafe to merge: #81, #17.

Repository-owner approval is still required before closing any historical PR.
No current PR head should be merged directly into `main`.
