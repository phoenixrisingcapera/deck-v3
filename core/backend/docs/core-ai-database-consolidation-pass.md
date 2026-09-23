# Core And AI Database Consolidation Pass

## Scope

This pass aligned runtime behavior toward a two-database target:

- Core Postgres owns product transactions, auth/session truth, billing truth, workflows, and mounted product artifacts.
- AI Postgres with pgvector owns embeddings, retrieval support data, training export rows, and evaluation support data.

## Implemented

- Auth and billing dependencies now prefer Core DB by default.
- Legacy user and billing database URLs remain fallback-only during the migration window.
- Smart Deck responses now expose DashScope/Qwen models instead of hiding them.
- Qwen defaults were aligned to:
  - generation: `qwen3.7-plus`
  - critique: `qwen-plus`
  - repair: `qwen-turbo`
- Vector retrieval and vector chunk sync now fail soft:
  - retrieval returns `unavailable` instead of crashing requests
  - chunk sync returns `degraded` instead of breaking product flows when vector storage is unavailable
- User-instruction vector chunk keys are now stable across processes.
- Shared structured JSON LLM execution now supports DashScope/Qwen in addition to Anthropic, OpenAI, and OpenRouter.
- Qwen multimodal vision transport now exists for structured JSON workflows.
- Smart Edit, Due Diligence, Audience Conversion, Market Research, and Deck Map analysis now pass slide preview image URLs to Qwen vision when public slide images are available.

## Verification

- `tests/test_auth_route_security.py`
- `tests/test_auth_sessions.py`
- `tests/test_billing_subscription_service.py`
- `tests/test_smart_deck_route_security.py`
- `tests/test_source_pipeline_optional_brand_contract.py`
- `tests/test_qwen_structured_json_and_vision.py`

## Deferred

- Physical Railway data migration from user and billing DBs into Core
- Physical migration of training/export support data into AI DB
- Clean separation of vector storage from Core schema ownership
- Full runtime production verification against Railway-backed deck flows
