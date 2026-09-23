# Provider Architecture And Re-enablement Guide

Date: 2026-07-20

This document records the provider behavior that is mounted and enabled now,
the compatibility transports that remain in source, and the work required to
re-enable a broader provider set safely.

It does not claim that every provider transport is currently selectable in the
product. Runtime truth comes from the configured Railway environment, the
mounted frontend provider modal, the backend resolver, and a real provider
request.

## Current Production Contract

OpenAI is the configured default for generation and embeddings:

| Capability | Active provider | Default model | Current status |
|---|---|---|---|
| Smart Deck and related text generation | OpenAI | `gpt-5` | Mounted and wired; live quota/capacity proof is still required |
| Critique and repair | OpenAI | `gpt-5` | Uses the resolved generation provider |
| Vision-capable structured generation | OpenAI | `gpt-5` | Wired where the calling workflow supplies visual input |
| Embeddings | OpenAI | `text-embedding-3-small`, 1024 dimensions | Configured; `/api/health/ai` performs the live embedding probe |
| Workspace BYOK | OpenAI | Catalog defaults above | Mounted and wired for same-provider generation credentials |

The latest provider audit reached OpenAI successfully but received HTTP 429
`insufficient_quota`. Therefore, configuration and static tests do not prove
that production generation can currently complete.

## Canonical Runtime Flow

```text
Canonical product route
-> mounted SvelteKit component
-> product-scoped frontend proxy
-> FastAPI product route
-> durable workflow job where the operation is asynchronous
-> provider configuration resolution
-> OpenAI transport
-> persisted workflow/design/telemetry artifacts
-> frontend polling and rendered result
```

No provider-specific alternate product route is canonical. The mounted product
route tree remains the route source of truth.

## Generation Provider Resolution

The principal generation contract is owned by
`app/services/llm/generation_service.py`.

In production it resolves in this order:

1. Read `DECK_GENERATION_MODE`.
2. Load a workspace credential only when its provider matches the production
   provider selected by Railway.
3. Otherwise use the environment credential for the selected provider.
4. Fail explicitly when the selected provider has no usable credential.

`app/ai_orchestration/provider_resolver.py` applies the same same-provider rule
for the orchestration compatibility path. A stale workspace preference cannot
silently route around the Railway-selected production provider.

OpenAI and Qwen/DashScope have active resolver branches. Direct Anthropic and
OpenRouter environment and workspace branches are retained as commented
compatibility code and are not active production contracts.

## Embedding Resolution

`app/services/llm/embedding_service.py` owns the embedding contract.

Production behavior is deliberately strict:

- `EMBEDDING_PROVIDER=openai` uses OpenAI only.
- `EMBEDDING_PROVIDER=dashscope` uses DashScope only.
- Production does not fall through to an off-platform or local provider after
  an explicitly configured provider fails.
- Every persisted vector must have 1024 dimensions.

Non-production compatibility mode may try configured cloud providers and then
the local sentence-transformers fallback. That behavior must not be described
as the production fallback policy.

Workspace-specific embedding resolution currently exists for Qwen/DashScope.
An OpenAI workspace BYOK key is used by generation, while the configured
environment OpenAI key owns the current production embedding path.

## Provider Capability Matrix

| Provider | Transport code present | Environment generation | Mounted BYOK tab | Production status |
|---|---:|---:|---:|---|
| OpenAI | Yes | Enabled | Enabled | Active default |
| Qwen / DashScope | Yes | Resolver support retained | Disabled in mounted UI | Explicit compatibility/specialized path; not the default |
| Anthropic | Yes | Disabled in principal resolver | Disabled | Compatibility transport only |
| OpenRouter | Yes | Disabled in principal resolver | Disabled | Compatibility transport only |

Transport code being present does not make a provider mounted, enabled, or
production-ready.

## Current OpenAI Configuration

Set non-secret values and the secret on the API and every worker that performs
generation, diligence, source enrichment, or embeddings:

```env
DECK_GENERATION_MODE=openai
DECK_LLM_PROVIDER=openai
OPENAI_API_KEY=<secret>
OPENAI_MODEL=gpt-5
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1024
```

Do not assume a fixed number of Railway services. Apply provider configuration
to the API and all LLM-capable worker roles in the deployed topology.

## Workspace BYOK

The mounted `WorkspaceAiProviderModal.svelte` currently exposes OpenAI only.
The Qwen, Anthropic, and OpenRouter tabs remain commented for compatibility and
future re-enablement.

The active flow is:

1. The user opens the workspace AI configuration from the mounted product UI.
2. The user supplies an OpenAI key and compatible catalog models.
3. The backend validates the credential before persistence.
4. The key is encrypted with Fernet and stored against that workspace.
5. Generation uses the workspace credential only for the matching active
   production provider.
6. Revocation deactivates the stored credential and returns the workspace to
   the platform provider.

The API returns masked credential metadata, never the decrypted key.

## Re-enabling Another Provider

Changing environment variables alone is not sufficient for Anthropic,
OpenRouter, or mounted Qwen BYOK.

Before re-enabling a provider:

1. Enable its capability in `app/services/llm/model_catalog.py`.
2. Restore the intentionally commented resolver branches in
   `app/ai_orchestration/provider_resolver.py` and
   `app/services/llm/generation_service.py` where required.
3. Restore the matching mounted tab in
   `WorkspaceAiProviderModal.svelte` only after the backend contract is active.
4. Verify workspace credential validation, encryption, revocation, and strict
   cross-workspace isolation.
5. Decide the embedding provider explicitly. Anthropic has no embedding API;
   OpenRouter embedding support is compatibility code, not the active
   production contract.
6. Add or update focused provider, route, worker, persistence, and health tests.
7. Deploy the API and every affected worker with matching non-secret settings
   and secret coverage.
8. Run a bounded live provider probe, then an authenticated canonical workflow
   through persistence and rendered reload.

Keep old implementation visible and documented when restoring disabled code,
in accordance with the repository preservation rules.

## Database Requirements

Production uses two PostgreSQL database roles:

| Database | Ownership |
|---|---|
| Core, via `DATABASE_URL` | Users, workspaces, decks, slides, workflow commands, and transactional product state |
| AI, via `AI_DATABASE_URL` | pgvector data, embeddings, AI telemetry, and rebuildable AI support state |

The AI database must have the `vector` extension and the `vector_chunks`
embedding column must be `vector(1024)`. Production does not use the local
single-database compatibility fallback.

## Health And Runtime Proof

Use both checks for different evidence:

```bash
curl https://api.deck.aistack.codes/api/health/product-ready
curl https://api.deck.aistack.codes/api/health/ai
```

`/api/health/product-ready` checks database migration state, AI database vector
shape, storage readiness, and generation provider key/model presence. Its
provider result does not make a live generation request.

`/api/health/ai` also calls the configured embedding provider and validates the
returned vector shape. Neither endpoint replaces an authenticated product flow
that proves generation, artifact persistence, polling, and rendered reload.

Provider configuration is complete only when all of the following are true:

- the canonical route and mounted component invoke the real backend contract;
- the owning worker has the required provider configuration;
- a live provider request succeeds;
- the workflow reaches its durable terminal state;
- generated artifacts persist and reload;
- errors are redacted and classified without exposing credentials.

## Key Ownership Files

| File | Ownership |
|---|---|
| `app/core/config.py` | Provider defaults, environment aliases, and production validation |
| `app/services/llm/generation_service.py` | Main generation provider and workspace-credential resolution |
| `app/ai_orchestration/provider_resolver.py` | Orchestration compatibility provider resolution |
| `app/services/llm/openai_provider.py` | OpenAI Responses API transport |
| `app/services/llm/dashscope_provider.py` | Qwen/DashScope transport and embeddings |
| `app/services/llm/anthropic_provider.py` | Retained Anthropic transport |
| `app/services/llm/openrouter_provider.py` | Retained OpenRouter transport |
| `app/services/llm/embedding_service.py` | Embedding selection, calls, dimension validation, and metrics |
| `app/services/llm/model_catalog.py` | Mounted provider/model capability policy |
| `app/services/platform/shell/workspace_ai_provider_service.py` | Workspace credential validation, encryption, persistence, and revocation |
| `app/api/routes/health.py` | Product and AI readiness contracts |
| Frontend repo: `src/lib/components/WorkspaceAiProviderModal.svelte` | Mounted workspace provider UI policy |

## Security Boundaries

- Never commit provider keys or decrypted credential values.
- Workspace credentials are encrypted before persistence and returned only as
  masked metadata.
- Production workspace credentials must match the Railway-selected provider.
- Provider failures exposed to product users must be redacted and categorized.
- Key/model presence is configuration evidence, not provider authorization,
  quota, capacity, or end-to-end production proof.
