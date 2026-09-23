# DeckAiStack LLM Knowledge Runtime Audit

## Goal

Make the LLM knowledge layer easier to verify in production and expose the current weak points in the backend/frontend connection.

The backend already had the right foundation:

- compiled deck archetype loading
- admin health endpoint
- Smart Deck and Smart Edit knowledge context
- runtime artifacts in the service layer

This PR adds runtime visibility for the missing pieces without moving model logic into the frontend.

## What this PR adds

### 1. Market research knowledge runtime loader

Added:

```text
app/ai/market_research_knowledge_context.py
```

The loader can read market research knowledge from:

- `MARKET_RESEARCH_KNOWLEDGE_PATH`
- extracted source directory
- zip archive
- direct JSON file

It exposes market verification context separately from slide classification context.

### 2. Extended LLM knowledge health

Updated:

```text
app/services/llm_knowledge_service.py
```

Health now covers:

- deck archetypes
- due diligence
- architecture runtime
- market research
- task contracts

Task contracts now explicitly distinguish:

- slide classification
- block classification
- market verification

### 3. Reload and task routes

Added:

```text
app/api/routes/llm_knowledge_admin.py
```

Routes:

```text
GET  /api/admin/llm-knowledge/tasks
POST /api/admin/llm-knowledge/reload
GET  /api/admin/llm-knowledge/full-health
```

Existing route remains:

```text
GET /api/admin/llm-knowledge/health
```

### 4. Contract verifier

Added:

```text
scripts/verify_llm_knowledge_contract.py
```

It verifies:

- required admin routes are registered
- health contains all required packages
- health contains slide/block/market task contracts
- task contracts include required outputs and artifact metadata

### 5. Instant Deck runtime knowledge pack

Added canonical runtime content under:

```text
llm_knowledge/instant_deck_knowledge_pack/
app/ai/instant_deck_knowledge_context.py
app/llm/prompt_packages/instant_deck/
```

This package provides:

- JSON runtime references derived from the supplied VC AiStack and Context Vigilance sources
- a default Instant Deck whole-deck prompt recipe
- a default embedding-seed source registry for future corpus indexing work
- additive runtime capabilities so the mounted frontend can request `generationMode=instant_deck` while staying on the canonical Smart Deck workflow endpoint

## Known remaining weaknesses

This PR does not fully implement production inference endpoints for classification and market verification.

Still needed:

- dedicated runtime endpoints for slide classification, block classification, and market verification
- persistence of `knowledge_pack_id` and `knowledge_pack_version` on every generated artifact
- explicit market verification artifacts beside classification artifacts
- frontend review surfaces for confidence, evidence, missing inputs, and unsupported claims
- CI execution of the verifier script

## Acceptance criteria

- Backend can report market research knowledge health separately from archetype health.
- Backend can reload cached knowledge without a deploy.
- Backend can report task contracts for slide classification, block classification, and market verification.
- Admin/frontend can call product-safe API routes without direct filesystem knowledge.
- Contract verifier exists for local/CI checks.

## Verification

Run from backend repo root:

```bash
python -m compileall -q app scripts
python scripts/verify_llm_knowledge_contract.py
```

The GitHub connector cannot run commands, so local or CI verification is still required before merge.
