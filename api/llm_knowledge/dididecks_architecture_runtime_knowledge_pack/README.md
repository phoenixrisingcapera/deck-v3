# DidiDecks / DeckAiStack Architecture Runtime Knowledge Pack

Created: 2026-06-20

This package turns the DidiDecks architecture into a reusable implementation and LLM knowledge pack.

It is built around one product rule:

> DidiDecks is not a static deck generator. It is a database-backed deck operating system where slides, blocks, persistent business fields, field usages, reviews, versions, rebuild jobs, exports, and access controls are all explicit product objects.

## What this pack contains

- Product architecture docs
- JSON knowledge files for the LLM/product planner
- JSON Schemas for deck editor, blocks, persistent fields, field usage, access, data assets, rebuild jobs, AI commands, and review matrix objects
- Codex-ready prompts for frontend, backend, guardrails, access, data assets, editor integration, and GitHub readiness
- SQL table blueprint for the DidiDecks backend module
- TypeScript type and API client contracts
- Local verification scripts for architecture drift and backend module boundaries
- Status templates for frontend, backend, guardrails, and repository verification

## Suggested install locations

For the frontend repo:

```txt
/deck-saas/docs/dididecks_pack/
/deck-saas/llm_knowledge/dididecks/
```

For the backend repo:

```txt
/aistack-backend/app/products/dididecks/docs/
/aistack-backend/app/products/dididecks/schemas/
```

For guardrails:

```txt
/aistack-guardrails/docs/dididecks/
/aistack-guardrails/policies/dididecks/
```

## Fast usage

1. Give `prompts/03_codex_editor_runtime_integration.md` to Codex when you want editor block selection + persistent-field binding.
2. Give `prompts/04_codex_backend_boundary.md` to Codex when you want the backend module isolated under `app/products/dididecks`.
3. Copy `json/architecture_drift_rules.json` into your guardrail logic.
4. Use `schemas/deck_editor_view_model.schema.json` to validate LLM or backend responses.
5. Use `scripts/verify_dididecks_repo.mjs` as a starting local verifier.

## Product principle

The editor, map, smart edit, rebuild, review matrix, and exports must not become separate mock products. They should all consume the same model:

```txt
Deck → Slides → Variants → Blocks → Persistent field bindings → Field usage map → Change preview → Rebuild job → Version/audit/export
```
