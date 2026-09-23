# OpenAI Platform Provider Release

**Date:** 2026-07-21

**Release tag:** `openai-platform-provider-2026-07-21`

**Target branch:** `main`

## Released behavior

Railway's shared production AI runtime is OpenAI-only:

- `DECK_GENERATION_MODE=openai`
- `DECK_LLM_PROVIDER=openai`
- `EMBEDDING_PROVIDER=openai`
- `OPENAI_API_KEY` supplies the shared platform credential
- `OPENAI_MODEL` supplies the current text and vision model
- `EMBEDDING_MODEL=text-embedding-3-small`
- `EMBEDDING_DIMENSIONS=1024`

Generation, structured JSON, repair, vision, orchestration, and platform embeddings reject shared Qwen/DashScope/OpenRouter/Anthropic routing in production. They do not silently change provider when an OpenAI request fails.

## Preserved workspace Qwen support

Qwen/DashScope transport code remains available for explicit workspace BYOK. In production, a Qwen request is allowed only when:

1. the workspace selected Qwen;
2. the key is stored as an encrypted `WorkspaceAiCredential` owned by that workspace;
3. the active setting references that credential;
4. the requested model belongs to the Qwen catalog and supports the operation;
5. downstream structured-generation and embedding calls receive `source=workspace`.

A missing, revoked, undecryptable, provider-mismatched, or cross-workspace credential fails closed. The resolver does not substitute `OPENAI_API_KEY`, `QWEN_API_KEY`, or another workspace's key.

Shared `QWEN_*` and `DASHSCOPE_*` Railway variables are documented as disabled compatibility examples. They are not part of the production API/worker contract.

## Code boundaries changed

- `app/core/config.py` enforces the OpenAI platform contract by production role.
- `app/ai_orchestration/provider_resolver.py` resolves explicit workspace credentials first, then enforces OpenAI for the shared environment path.
- `app/services/llm/generation_service.py` restricts environment provider resolution to OpenAI while retaining workspace provider resolution.
- `app/services/llm/structured_json_service.py` distinguishes shared environment calls from workspace BYOK calls.
- `app/services/llm/embedding_service.py` enforces OpenAI for platform embeddings and validates workspace provider/model/credential ownership for BYOK.
- `app/services/platform/shell/workspace_ai_provider_service.py` permits OpenAI and Qwen workspace credentials in production while keeping other providers inactive.
- `.env.railway.required` documents the API-owned OpenAI variables and disabled compatibility variables without containing real secrets.

## Verification contract

Focused tests cover:

- production configuration rejection of shared Qwen generation and embeddings;
- one first-party OpenAI platform embedding attempt with no cross-provider fallback;
- production provider resolution with OpenAI environment credentials;
- explicit workspace Qwen structured JSON and embeddings;
- encrypted workspace credential ownership and provider matching;
- actual provider/model persistence for vision artifacts;
- failure before network transport when a forbidden platform provider is selected.

Static and contract checks are necessary but not sufficient. Release acceptance requires a bounded live OpenAI generation, embedding, vision, Smart Edit, and Due Diligence request through the deployed API and worker paths. A readiness endpoint alone is not live-generation proof.

## Cost-routing follow-up

This release changes provider ownership; it does not yet implement task-based OpenAI model selection. The approved implementation direction is to introduce `fast`, `quality`, `vision`, and `embedding` tiers, start ordinary work on the inexpensive tier, use deterministic critique where possible, and allow only one validation-driven quality escalation.

Until that follow-up is implemented and tested, `OPENAI_MODEL` remains the compatibility setting. Operators should not claim that automatic cost-aware model selection is active.

## Rollback

Restore the previous deployment without adding shared Qwen variables. If OpenAI is unavailable, report the affected job as degraded or failed rather than silently changing providers. Workspace Qwen can be revoked independently by deactivating its workspace credential.
