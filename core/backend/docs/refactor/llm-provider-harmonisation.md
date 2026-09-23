# LLM Provider Harmonisation — Audit & Staged Refactor

## 1. Current LLM Call Sites

### 1.1 Provider implementation layer (`app/ai/`)

| File | Provider | What it does | Called by | Output shape | Saves artifacts? |
|------|----------|-------------|-----------|-------------|-----------------|
| `app/ai/llm_provider.py` | Anthropic | `call_anthropic_message()` — raw HTTP POST to `/v1/messages` with retry; `extract_anthropic_text()` — extracts text content block; `AnthropicProvider` — `AIProvider.complete()` adapter | `smart_deck_llm_service`, `agents/llm_agent_utils`, `workspace_ai_provider_service`, `ai_orchestration/providers/anthropic_provider`, `smart_deck_source_enrichment_service` | Raw `dict` from API; `str` from `extract_*` | No |
| `app/ai/anthropic_provider.py` | Anthropic | Re-export shim for `app.ai.llm_provider` | Backward-compat imports | — | No |
| `app/ai/openai_provider.py` | OpenAI | `call_openai_response()` — raw HTTP POST to `/v1/responses`; `extract_openai_text()`; `OpenAIProvider` — `AIProvider.complete()` adapter | `smart_deck_llm_service`, `agents/llm_agent_utils`, `workspace_ai_provider_service`, `ai_orchestration/providers/openai_provider`, `smart_deck_source_enrichment_service` | Raw `dict` from API; `str` from `extract_*` | No |
| `app/ai/openrouter_provider.py` | OpenRouter | `call_openrouter_chat_completion()` — raw HTTP POST to `/v1/chat/completions`; `extract_openrouter_text()`; `OpenRouterProvider` — `AIProvider.complete()` adapter | `smart_deck_llm_service`, `agents/llm_agent_utils`, `workspace_ai_provider_service`, `smart_deck_source_enrichment_service` | Raw `dict` from API; `str` from `extract_*` | No |
| `app/ai/provider.py` | — | `AIProvider` Protocol: `complete(system, user) -> dict[str, str]` | NOT USED by any application code | — | No |

### 1.2 Orchestration provider layer (`app/ai_orchestration/providers/`)

| File | Provider | What it does | Called by | Output shape | Saves artifacts? |
|------|----------|-------------|-----------|-------------|-----------------|
| `base.py` | — | `BaseLlmProvider` Protocol: `generate_slide_versions(context) -> LlmGenerationOutput` | `provider_resolver.py`, `orchestrator.py` | `LlmGenerationOutput` (Pydantic model) | No |
| `anthropic_provider.py` | Anthropic | `AnthropicLlmProvider.generate_slide_versions()` — calls `call_anthropic_message` with system prompt, parses JSON into `LlmGenerationOutput` | `provider_resolver.py` → `orchestrator.py` | `LlmGenerationOutput` (parsed JSON) | No |
| `openai_provider.py` | OpenAI | `OpenAiLlmProvider.generate_slide_versions()` — calls `call_openai_response` with system prompt, parses JSON into `LlmGenerationOutput` | `provider_resolver.py` → `orchestrator.py` | `LlmGenerationOutput` (parsed JSON) | No |
| `__init__.py` | — | Re-exports both providers | `provider_resolver.py` | — | No |

**Missing:** No `OpenRouterLlmProvider` in this layer.

### 1.3 Smart Deck generation call sites (`app/services/smart_deck_llm_service.py`)

| Function | Provider(s) | What it does | Output shape | Saves artifacts? |
|----------|------------|-------------|-------------|-----------------|
| `_call_anthropic_render_payload` | Anthropic | Calls `call_anthropic_message` with `_build_anthropic_prompt` | Parsed JSON dict | No |
| `_call_openai_render_payload` | OpenAI | Calls `call_openai_response` with `_build_anthropic_prompt` | Parsed JSON dict | No |
| `_call_openrouter_render_payload` | OpenRouter | Calls `call_openrouter_chat_completion` with `_build_anthropic_prompt` | Parsed JSON dict | No |
| `_generate_render_payload` | All 3 + deterministic | Dispatches to provider-specific `_call_*_render_payload` | Parsed JSON dict | No |
| `_call_anthropic_assistant_insight` | Anthropic | Calls `call_anthropic_message` with `_build_anthropic_assistant_prompt` | Parsed JSON dict | No |
| `_call_openai_assistant_insight` | OpenAI | Calls `call_openai_response` with `_build_anthropic_assistant_prompt` | Parsed JSON dict | No |
| `_call_openrouter_assistant_insight` | OpenRouter | Calls `call_openrouter_chat_completion` with `_build_anthropic_assistant_prompt` | Parsed JSON dict | No |
| `_generate_assistant_insight` | All 3 | Dispatches to provider-specific `_call_*_assistant_insight` | Parsed JSON dict | No |
| `_call_anthropic_render_payload` et al. | All 3 | Provider-specific prompt + API call + JSON extraction | Dict | No |
| `_build_anthropic_prompt` | — | Builds Anthropic-style prompt from `llm_context` | String | No |
| `_build_anthropic_assistant_prompt` | — | Builds assistant prompt from context dict | String | No |
| `_record_llm_artifact` | — | Saves artifact to `DeckLlmArtifact` table | DB row | Yes |
| `_write_render_schema_json_artifact` | — | Writes render schema to bucket storage + DB | Dict pointer | Yes |
| `_write_design_version_manifest_json_artifact` | — | Writes version manifest to bucket storage + DB | Dict pointer | Yes |
| `_critique_generated_render_payload` | — | Validates + critiques render payload (rule-based, no LLM) | Dict | No |
| `_build_repair_context` | — | Builds context dict for repair pass | Dict | No |
| `_repair_render_payload` | — | Calls LLM again with repair context | Dict | No |
| `create_generation_job` | — | Orchestrates full generation: context → prompt → call → validate → critique → repair → persist | Dict (job result) | Yes (artifacts) |

### 1.4 Agent utility call site (`app/agents/llm_agent_utils.py`)

| Function | Provider(s) | What it does | Output shape | Saves artifacts? |
|----------|------------|-------------|-------------|-----------------|
| `complete_json_with_ai_provider` | All 3 | `if provider == "anthropic"/"openai"/"openrouter"` chain, calls provider-specific function, extracts JSON | Parsed JSON payload | No |
| `complete_json_with_provider` | All 3 | Alias for `complete_json_with_ai_provider` | Parsed JSON payload | No |
| `extract_json_payload` | — | Strips markdown fences, finds JSON object/array | Parsed Python object | No |

### 1.5 Source enrichment call site (`app/services/smart_deck_source_enrichment_service.py`)

| Function | Provider(s) | What it does | Output shape | Saves artifacts? |
|----------|------------|-------------|-------------|-----------------|
| `_call_provider` | All 3 | `if provider == "openai"/"anthropic"` (fallback openrouter), calls provider API, returns text | Raw text string | No |
| `_resolve_provider_config` | All 3 | Reads `deck_generation_mode` setting, returns provider/model/apiKey | Dict with provider, model, apiKey | No |
| `_parse_json_response` | — | Strips markdown fences, parses JSON | Dict | No |
| `enrich_source_labels_with_llm` | All 3 | Orchestrates: resolve → call → parse → validate → return result | Dict with status/used/validated/error | No |

### 1.6 Workspace AI provider validation (`app/services/workspace_ai_provider_service.py`)

| Function | Provider(s) | What it does | Output shape | Saves artifacts? |
|----------|------------|-------------|-------------|-----------------|
| `_validate_claude_connection` | Anthropic | Calls `call_anthropic_message` with test prompt | `str` (extracted text) | No |
| `_validate_openai_connection` | OpenAI | Calls `call_openai_response` with test prompt | `str` (extracted text) | No |
| `_validate_openrouter_connection` | OpenRouter | Calls `call_openrouter_chat_completion` with test prompt | `str` (extracted text) | No |
| `save_workspace_ai_provider` | All 3 | `if provider == "claude"/"openai"/"openrouter"` chain to validate, then encrypt + persist | Dict with summary | Yes (credential DB row) |

### 1.7 Orchestration provider resolution (`app/ai_orchestration/provider_resolver.py`)

| Function | Provider(s) | What it does | Output shape | Saves artifacts? |
|----------|------------|-------------|-------------|-----------------|
| `resolve_orchestration_provider` | OpenAI, Claude | Resolves workspace provider or falls back to env-based provider; returns `BaseLlmProvider` instance | `AnthropicLlmProvider` / `OpenAiLlmProvider` | No |
| `_resolve_workspace_provider` | OpenAI, Claude | Reads `WorkspaceAiProviderSetting`, decrypts API key | `BaseLlmProvider` or None | No |

**Notable:** `provider_resolver.py` has NO OpenRouter support. It resolves to OpenAi or Claude only. OpenRouter is handled only by `smart_deck_llm_service` (via `_resolve_claude_config`) and `smart_deck_source_enrichment_service`.

### 1.8 Orphaned generation modules

| File | Provider | Status |
|------|----------|--------|
| `app/services/generation/claude/claude_generate_slides.py` | Claude | ORPHANED — uses `call_anthropic_message` directly, not called by any active route or worker |
| `app/services/generation/claude/build_prompt.py` | Claude | Only called by `claude_generate_slides.py` |
| `app/services/generation/openai/openai_generate_slides.py` | OpenAI | ORPHANED — not called by any active route or worker |
| `app/services/generation/validate_generated_deck.py` | — | Used by both orphaned modules (actively called by `generation_runtime`) |

### 1.9 New LLM spine wrappers (`app/services/llm/`)

| File | What it does | Status |
|------|-------------|--------|
| `provider_base.py` | `LLMProvider` abstract base with `generate_text()` and `validate_connection()` | NEW — wraps `app/ai/*` functions |
| `provider_registry.py` | `ProviderRegistry` with `register()`/`get()` | NEW |
| `openai_provider.py` | `OpenAIProvider(LLMProvider)` — delegates to `app.ai.openai_provider` | NEW |
| `anthropic_provider.py` | `AnthropicProvider(LLMProvider)` — delegates to `app.ai.llm_provider` | NEW |
| `openrouter_provider.py` | `OpenRouterProvider(LLMProvider)` — delegates to `app.ai.openrouter_provider` | NEW |
| `generation_service.py` | Re-exports from `smart_deck_llm_service`; exposes `generate_text()` via registry | NEW — spine wrapper |
| `assistant_service.py` | Re-exports `create_smart_deck_assistant_run` | NEW — spine wrapper |
| `critique_service.py` | Re-exports from `app.services.critique_service` | NEW — thin re-export |
| `repair_service.py` | Re-exports from `smart_deck_output_validation` | NEW — thin re-export |
| `artifact_service.py` | Re-exports from `smart_deck_artifact_writer` | NEW — thin re-export |
| `prompt_builder.py` | Re-exports from `smart_deck_prompt_builder` | NEW — thin re-export |
| `response_models.py` | `LlmResponse`, `LlmGenerationConfig` dataclasses | NEW |
| `__init__.py` | Auto-registers all 3 providers into `default_registry` | NEW |

---

## 2. Duplicate Responsibility Audit

### 2.1 Provider API calls — 3 functions doing the same thing per provider

Each provider has 3+ functions that wrap the same API call with different parameters:

| Provider | Functions that call the API | Files |
|----------|---------------------------|-------|
| Anthropic | `call_anthropic_message`, `_call_anthropic_render_payload`, `_call_anthropic_assistant_insight`, `_validate_claude_connection`, `AnthropicLlmProvider.generate_slide_versions`, `claude_generate_slides.py`, `complete_json_with_ai_provider` | 7 files |
| OpenAI | `call_openai_response`, `_call_openai_render_payload`, `_call_openai_assistant_insight`, `_validate_openai_connection`, `OpenAiLlmProvider.generate_slide_versions`, `openai_generate_slides.py`, `complete_json_with_ai_provider` | 7 files |
| OpenRouter | `call_openrouter_chat_completion`, `_call_openrouter_render_payload`, `_call_openrouter_assistant_insight`, `_validate_openrouter_connection`, `complete_json_with_ai_provider` | 5 files |

### 2.2 Prompt construction — 2 conflicting approaches

| Approach | Files | Details |
|----------|-------|---------|
| `_build_anthropic_prompt(llm_context)` | `smart_deck_llm_service.py:1790` | Builds a single large prompt string from llm_context dict |
| `_build_anthropic_assistant_prompt(context)` | `smart_deck_llm_service.py:3978` | Builds assistant-specific prompt from context dict |
| `build_system_prompt()` / `build_user_prompt()` | `app/services/generation/claude/build_prompt.py` | Orphaned, only used by `claude_generate_slides.py` |
| `app/ai/vc_prompt_context.py` | Called from `_build_assistant_context` | Builds VC audience context dict (not a prompt string) |
| `app/ai/slide_archetypes_context.py` | Called from `_build_assistant_context` | Builds slide archetype context dict |
| `app/ai/architecture_runtime_context.py` | Called from `get_smart_deck_workspace` | Builds runtime capabilities dict |

### 2.3 Response validation — 2 implementations

| Implementation | Files | Used by |
|---------------|-------|---------|
| `_extract_json_payload(raw_text)` | `smart_deck_llm_service.py:1778` | `smart_deck_llm_service` |
| `extract_json_payload(raw_text)` | `app/agents/llm_agent_utils.py:20` | `llm_agent_utils` |
| `_parse_json_response(text)` | `smart_deck_source_enrichment_service.py:134` | `source_enrichment_service` |
| `_extract_json_response(payload)` | `ai_orchestration/providers/openai_provider.py:41` | `OpenAiLlmProvider` |

All 4 do approximately the same thing: strip markdown fences, find JSON braces, call `json.loads`. They should be unified.

### 2.4 Critique logic — 2 layers

| Layer | File | What it does |
|-------|------|-------------|
| `build_critique_decision` | `app/services/critique_service.py` | Rule-based critique: checks factuality, evidence, safety flags, edit quality |
| `_critique_generated_render_payload` | `smart_deck_llm_service.py:1956` | LLM-based critique: calls the generation provider again with a critique prompt |
| `summarize_critique_decisions` | `app/services/critique_service.py` | Aggregates multiple critique decisions |

### 2.5 Repair logic — 2 approaches

| Approach | File | What it does |
|----------|------|-------------|
| `_repair_render_payload` | `smart_deck_llm_service.py:2104` | Calls LLM again with repair context to fix generation output |
| `validate_source_labels` | `smart_deck_output_validation.py` | Validates source labels against known slide/block IDs (no LLM call) |

### 2.6 Artifact persistence — multiple paths

| Path | Function | File |
|------|----------|------|
| DB + bucket | `_record_llm_artifact` + `_write_json_artifact_to_storage` | `smart_deck_llm_service.py:1501` |
| Bucket only (canonical) | `persist_canonical_llm_artifact` | `llm_artifact_persistence_service.py` |
| Bucket only | `_write_render_schema_json_artifact`, `_write_code_metadata_json_artifact`, `_write_design_version_manifest_json_artifact` | `smart_deck_llm_service.py:1580` |
| DB only | `_record_llm_artifact` | `smart_deck_llm_service.py:1501` |
| Bucket + DB (artifacts) | `smart_deck_artifact_writer.write_source_v1_artifacts` | `smart_deck_artifact_writer.py` |

### 2.7 Model selection / fallback policy — scattered

| Function | File | What it does |
|----------|------|-------------|
| `_model_for_provider` | `smart_deck_llm_service.py:208` | Maps provider to model string with preference/setting fallback |
| `_provider_from_generation_mode` | `smart_deck_llm_service.py:228` | Maps `deck_generation_mode` to provider name |
| `_resolve_claude_config` | `smart_deck_llm_service.py:250` | Full provider config resolution: workspace key → env key → fallback |
| `_resolve_environment_provider_config` | `smart_deck_llm_service.py:296` | Env-only provider config resolution |
| `get_generation_provider_config` | `smart_deck_llm_service.py:368` | Public entrypoint for provider config |
| `_resolve_provider_config` | `smart_deck_source_enrichment_service.py:91` | Independent provider resolution for enrichment |
| `resolve_orchestration_provider` | `ai_orchestration/provider_resolver.py:14` | Independent provider resolution for orchestration |

**Key issue:** Provider resolution logic is duplicated across 3 layers with different fallback chains:

1. `smart_deck_llm_service._resolve_claude_config`: workspace credential → env var → `missing_*` sentinel
2. `smart_deck_source_enrichment_service._resolve_provider_config`: `deck_generation_mode` → specific provider, NO workspace credential support, NO fallback chain
3. `ai_orchestration/provider_resolver.resolve_orchestration_provider`: workspace credential → mode-based → env var, NO OpenRouter

### 2.8 Retry policy — inconsistent

| Provider | Retry? | Config |
|----------|--------|--------|
| Anthropic (in `app/ai/llm_provider.py`) | YES | `anthropic_max_retries`, `anthropic_retry_delay_seconds` |
| OpenAI (in `app/ai/openai_provider.py`) | NO | No retry logic |
| OpenRouter (in `app/ai/openrouter_provider.py`) | NO | No retry logic |

Anthropic has bounded retry for 429/5xx. OpenAI and OpenRouter fail immediately on any HTTP error.

---

## 3. Target `app/services/llm/` Folder Structure

```
app/services/llm/
├── __init__.py               — auto-registers providers into default_registry
├── provider_base.py          — LLMProvider abstract base (generate_text, validate_connection)
├── provider_registry.py      — ProviderRegistry (register/get/available)
├── openai_provider.py        — OpenAI implementation of LLMProvider
├── anthropic_provider.py     — Anthropic/Claude implementation of LLMProvider
├── openrouter_provider.py    — OpenRouter implementation of LLMProvider
├── prompt_builder.py         — Prompt construction helpers (centralised)
├── generation_service.py     — Provider-neutral generation orchestration
├── critique_service.py       — Critique logic (rule-based + LLM-based)
├── repair_service.py         — Repair pass logic
├── artifact_service.py       — LLM artifact persistence
├── response_models.py        — LlmResponse, LlmGenerationConfig
├── assistant_service.py      — Assistant run orchestration
└── provider_client.py        — Registry convenience functions
```

### Target ownership

| File | Owns | Does not own |
|------|------|-------------|
| `provider_base.py` | Common `LLMProvider` interface with `generate_text(system, user, config) -> LlmResponse` and `validate_connection(api_key) -> bool` | Prompt construction, response parsing, artifact saving |
| `provider_registry.py` | Provider selection: `register(name, provider)`, `get(name) -> LLMProvider` | Provider configuration (keys, models), model selection logic |
| `openai_provider.py` | OpenAI API transport: HTTP POST to `/v1/responses`, response extraction, error handling | Prompt building, response validation, critique, repair |
| `anthropic_provider.py` | Anthropic API transport: HTTP POST to `/v1/messages`, response extraction, retry logic | Prompt building, response validation, critique, repair |
| `openrouter_provider.py` | OpenRouter API transport: HTTP POST to `/v1/chat/completions`, response extraction | Prompt building, response validation, critique, repair |
| `prompt_builder.py` | Centralised prompt construction: `build_generation_prompt(context)`, `build_assistant_prompt(context)`, `build_critique_prompt(context)` | Provider API calls, response parsing |
| `generation_service.py` | Provider-neutral generation orchestration: resolve provider → build prompt → call LLM → parse → validate | Provider API transport, prompt construction internals |
| `critique_service.py` | Critique: `build_critique_decision(warnings, ...)` + `critique_generated_output(output, context)` | Provider API calls, generation |
| `repair_service.py` | Repair pass: `repair_generated_output(output, critique, context)` | Provider API calls, critique |
| `artifact_service.py` | LLM artifact persistence: `record_llm_artifact(db, ...)`, `persist_canonical_artifact(...)` | Generation, critique, repair |
| `response_models.py` | `LlmResponse`, `LlmGenerationConfig` | — |
| `assistant_service.py` | Assistant run orchestration (depends on `generation_service`) | — |

---

## 4. Proposed Staged Refactor

### Stage A — Audit only (this document)
**No runtime changes.** Verify the audit is accurate, discuss priorities.

**Verification:** none needed.

### Stage B — Introduce provider-neutral interface
**No breaking changes.** The existing `app/ai/*` functions continue to work. New files are additive.

Steps:
1. ✅ `response_models.py` — `LlmResponse`, `LlmGenerationConfig` (DONE)
2. ✅ `provider_base.py` — `LLMProvider` abstract base (DONE)
3. ✅ `provider_registry.py` — `ProviderRegistry` with `default_registry` (DONE)
4. ✅ `openai_provider.py` — wraps `app.ai.openai_provider` (DONE)
5. ✅ `anthropic_provider.py` — wraps `app.ai.llm_provider` (DONE)
6. ✅ `openrouter_provider.py` — wraps `app.ai.openrouter_provider` (DONE)
7. ✅ `__init__.py` — auto-registers into `default_registry` (DONE)

**Changed files:** All under `app/services/llm/` — new files only.
**Duplicate ownership removed:** None yet (old files unchanged).
**Files still duplicated:** All existing duplicates remain.
**Prune candidates:** None.

**Verification:**
```bash
python3 -m py_compile app/services/llm/__init__.py \
  app/services/llm/provider_base.py \
  app/services/llm/provider_registry.py \
  app/services/llm/response_models.py \
  app/services/llm/anthropic_provider.py \
  app/services/llm/openai_provider.py \
  app/services/llm/openrouter_provider.py
```

### Stage C — Migrate provider dispatch in `smart_deck_llm_service.py`

Replace the `if provider == "anthropic"/"openai"/"openrouter"` chains in:
- `_generate_render_payload` → use `_RENDER_PAYLOAD_PROVIDERS` dict dispatch ✅ (DONE)
- `_generate_assistant_insight` → use `_ASSISTANT_INSIGHT_PROVIDERS` dict dispatch ✅ (DONE)

**Changed files:** `app/services/smart_deck_llm_service.py`
**Duplicate ownership removed:** Provider dispatch logic consolidated into dict lookups.
**Files still duplicated:** `app/ai/*` provider implementations still duplicated with `app/services/llm/*` wrappers.
**Prune candidates:** None.

**Verification:**
```bash
python3 -m py_compile app/services/smart_deck_llm_service.py
```

### Stage D — Migrate remaining call sites

Replace direct `call_anthropic_message` / `call_openai_response` / `call_openrouter_chat_completion` calls with provider-neutral `LLMProvider.generate_text()` via the registry.

Sites to migrate (in priority order):

1. `app/agents/llm_agent_utils.py:complete_json_with_ai_provider` — the `if provider == "anthropic"/"openai"/"openrouter"` chain
2. `app/services/smart_deck_source_enrichment_service.py:_call_provider` — the `if provider == "openai"/"anthropic"` chain
3. `app/services/workspace_ai_provider_service.py:_validate_*_connection` — three separate validation functions
4. `app/ai_orchestration/provider_resolver.py` — add OpenRouter support through the registry
5. `app/services/generation/claude/claude_generate_slides.py` — if actively used
6. `app/services/generation/openai/openai_generate_slides.py` — if actively used

**Changed files:** All of the above.
**Duplicate ownership removed:** Provider-specific API calls replaced with registry dispatch.
**Files still duplicated:** Old `_call_*_render_payload` / `_call_*_assistant_insight` functions remain in `smart_deck_llm_service.py`.
**Prune candidates:** `app/services/generation/claude/`, `app/services/generation/openai/`.

**Verification:**
```bash
# All imports work
python3 -c "from app.services.llm.generation_service import generate_text; print('generate_text OK')"
python3 -c "from app.services.llm import default_registry; print('registry OK')"

# Provider config still loads
python3 -c "from app.services.smart_deck_llm_service import get_generation_provider_config; print('provider config OK')"

# Agent utils still works
python3 -c "from app.agents.llm_agent_utils import complete_json_with_ai_provider; print('agent utils OK')"

# Workspace provider validation still works
python3 -c "from app.services.workspace_ai_provider_service import save_workspace_ai_provider; print('workspace provider OK')"
```

### Stage E — Prune old provider-specific helpers

Only after ALL imports from old paths are redirected:

1. Replace `smart_deck_llm_service.py:_call_anthropic_render_payload` with registry-based call through `generation_service`
2. Remove `app/ai/anthropic_provider.py` (re-export shim, dead code)
3. Remove `app/ai_orchestration/providers/` directory (replaced by `app/services/llm/*`)
4. Consolidate `app/services/generation/claude/` + `app/services/generation/openai/` into `app/services/llm/`
5. Consolidate duplicate JSON extraction functions into `response_models.py`

**Changed files:** Multiple removals + rewrites.
**Duplicate ownership removed:** Old `app/ai/*` provider implementations merged into `app/services/llm/*`.
**Files still duplicated:** None after this stage.
**Prune candidates:**
- `app/ai/anthropic_provider.py` (re-export shim)
- `app/ai_orchestration/providers/` (replaced by `app/services/llm/`)
- `app/services/generation/claude/` (orphaned)
- `app/services/generation/openai/` (orphaned)
- `app/services/slide_thumbnail_service.py` (separate concern, pruned in spine cleanup)

**Verification:**
```bash
# Full test suite
python3 -m pytest tests/ -q 2>&1 | tail -5

# Smart Deck generation still works
python3 -c "from app.services.smart_deck_llm_service import create_generation_job; print('generation OK')"

# LLM artifacts still saved
python3 -c "from app.services.llm.artifact_service import persist_canonical_llm_artifact; print('artifacts OK')"

# Critique/repair still run
python3 -c "from app.services.llm.critique_service import build_critique_decision; print('critique OK')"

# Verify all imports resolve
python3 -c "
from app.services.llm import default_registry, LLMProvider, LlmGenerationConfig, LlmResponse
from app.services.llm.generation_service import generate_text
from app.services.llm.assistant_service import create_smart_deck_assistant_run
from app.services.llm.provider_client import get_provider
print('All imports OK')
"
```

---

## 5. Complete File Inventory

### Files that import provider-specific functions

| File | What it imports | From |
|------|----------------|------|
| `app/services/smart_deck_llm_service.py` | `call_anthropic_message`, `extract_anthropic_text` | `app.ai.anthropic_provider` |
| `app/services/smart_deck_llm_service.py` | `call_openai_response`, `extract_openai_text` | `app.ai.openai_provider` |
| `app/services/smart_deck_llm_service.py` | `call_openrouter_chat_completion`, `extract_openrouter_text` | `app.ai.openrouter_provider` |
| `app/agents/llm_agent_utils.py` | `call_anthropic_message`, `extract_anthropic_text` | `app.ai.anthropic_provider` |
| `app/agents/llm_agent_utils.py` | `call_openai_response`, `extract_openai_text` | `app.ai.openai_provider` |
| `app/agents/llm_agent_utils.py` | `call_openrouter_chat_completion`, `extract_openrouter_text` | `app.ai.openrouter_provider` |
| `app/services/smart_deck_source_enrichment_service.py` | `call_anthropic_message`, `extract_anthropic_text` | `app.ai.anthropic_provider` |
| `app/services/smart_deck_source_enrichment_service.py` | `call_openai_response`, `extract_openai_text` | `app.ai.openai_provider` |
| `app/services/smart_deck_source_enrichment_service.py` | `call_openrouter_chat_completion`, `extract_openrouter_text` | `app.ai.openrouter_provider` |
| `app/services/workspace_ai_provider_service.py` | `call_anthropic_message`, `extract_anthropic_text` | `app.ai.anthropic_provider` |
| `app/services/workspace_ai_provider_service.py` | `call_openai_response`, `extract_openai_text` | `app.ai.openai_provider` |
| `app/services/workspace_ai_provider_service.py` | `call_openrouter_chat_completion`, `extract_openrouter_text` | `app.ai.openrouter_provider` |
| `app/ai_orchestration/providers/anthropic_provider.py` | `call_anthropic_message`, `extract_anthropic_text` | `app.ai.anthropic_provider` |
| `app/ai_orchestration/providers/openai_provider.py` | `call_openai_response`, `extract_openai_text` | `app.ai.openai_provider` |
| `app/services/generation/claude/claude_generate_slides.py` | `call_anthropic_message`, `extract_anthropic_text` | `app.ai.anthropic_provider` |
| `app/services/generation/openai/openai_generate_slides.py` | (self-contained, imports from `app.ai.openai_provider`) | — |

### Files that define provider functionality

| File | Defines | Used by |
|------|---------|---------|
| `app/ai/llm_provider.py` | `call_anthropic_message`, `extract_anthropic_text`, `AnthropicProvider` | 5 files |
| `app/ai/anthropic_provider.py` | Re-exports from `llm_provider` | Backward compat |
| `app/ai/openai_provider.py` | `call_openai_response`, `extract_openai_text`, `OpenAIProvider` | 5 files |
| `app/ai/openrouter_provider.py` | `call_openrouter_chat_completion`, `extract_openrouter_text`, `OpenRouterProvider` | 4 files |
| `app/ai/provider.py` | `AIProvider` Protocol | 0 files (dead) |
| `app/ai_orchestration/providers/base.py` | `BaseLlmProvider` Protocol | `provider_resolver.py`, `orchestrator.py` |
| `app/ai_orchestration/providers/anthropic_provider.py` | `AnthropicLlmProvider` | `provider_resolver.py` |
| `app/ai_orchestration/providers/openai_provider.py` | `OpenAiLlmProvider` | `provider_resolver.py` |
| `app/services/llm/provider_base.py` | `LLMProvider` ABC | New wrappers |
| `app/services/llm/openai_provider.py` | `OpenAIProvider(LLMProvider)` | New wrappers |
| `app/services/llm/anthropic_provider.py` | `AnthropicProvider(LLMProvider)` | New wrappers |
| `app/services/llm/openrouter_provider.py` | `OpenRouterProvider(LLMProvider)` | New wrappers |

### Files with prompt construction logic

| File | What it builds |
|------|---------------|
| `app/services/smart_deck_llm_service.py:1790` | `_build_anthropic_prompt` — generation prompt from llm_context |
| `app/services/smart_deck_llm_service.py:3978` | `_build_anthropic_assistant_prompt` — assistant prompt from context |
| `app/services/generation/claude/build_prompt.py` | `build_system_prompt`, `build_user_prompt` — generation prompts |
| `app/ai/vc_prompt_context.py` | VC audience context dict |
| `app/ai/slide_archetypes_context.py` | Slide archetype context dict |
| `app/ai/architecture_runtime_context.py` | Runtime capabilities dict |
| `app/services/smart_deck_prompt_builder.py` | `build_source_enrichment_prompt`, `build_source_v1_context` |
| `app/ai/prompts.py` | `SMART_EDIT_SYSTEM_PROMPT`, `ANALYSIS_SYSTEM_PROMPT` constants |

### Files with response validation / JSON extraction logic

| File | Function | Notes |
|------|----------|-------|
| `app/services/smart_deck_llm_service.py:1778` | `_extract_json_payload` | Strips fences, finds JSON |
| `app/agents/llm_agent_utils.py:20` | `extract_json_payload` | Strips fences, finds JSON/array |
| `app/services/smart_deck_source_enrichment_service.py:134` | `_parse_json_response` | Strips fences, calls json.loads |

### Files with critique logic

| File | Function | Rule-based or LLM? |
|------|----------|-------------------|
| `app/services/critique_service.py` | `build_critique_decision` | Rule-based |
| `app/services/critique_service.py` | `summarize_critique_decisions` | Rule-based |
| `app/services/smart_deck_llm_service.py:1956` | `_critique_generated_render_payload` | LLM-based (calls provider again) |

### Files with repair logic

| File | Function | LLM-based? |
|------|----------|-----------|
| `app/services/smart_deck_llm_service.py:2104` | `_repair_render_payload` | Yes (calls provider again) |
| `app/services/smart_deck_output_validation.py` | `validate_source_labels` | No (rule-based validation) |

### Files with artifact persistence

| File | Function | Storage target |
|------|----------|---------------|
| `app/services/smart_deck_llm_service.py:1501` | `_record_llm_artifact` | DB (`DeckLlmArtifact`) |
| `app/services/smart_deck_llm_service.py:1563` | `_write_json_artifact_to_storage` | Bucket storage |
| `app/services/llm_artifact_persistence_service.py` | `persist_canonical_llm_artifact` | Bucket storage (canonical path) |
| `app/services/smart_deck_artifact_writer.py` | `write_source_v1_artifacts` | Bucket + DB |
| `app/services/smart_deck_llm_service.py:1580` | `_write_render_schema_json_artifact` | Bucket + DB |
| `app/services/smart_deck_llm_service.py:1607` | `_write_code_metadata_json_artifact` | Bucket + DB |
| `app/services/smart_deck_llm_service.py:1634` | `_write_design_version_manifest_json_artifact` | Bucket + DB |

### Files with model selection / provider resolution

| File | Function(s) | Resolution order |
|------|-------------|-----------------|
| `smart_deck_llm_service.py` | `_resolve_claude_config`, `_resolve_environment_provider_config`, `_model_for_provider`, `_provider_from_generation_mode` | Workspace credential → env var → sentinel |
| `smart_deck_source_enrichment_service.py` | `_resolve_provider_config` | `deck_generation_mode` → specific provider (no workspace fallback) |
| `ai_orchestration/provider_resolver.py` | `resolve_orchestration_provider`, `_resolve_workspace_provider` | Workspace credential → mode → env var (no OpenRouter) |

---

## 6. Key Risks

1. **OpenRouter gap in orchestration layer:** `ai_orchestration/provider_resolver.py` has no OpenRouter provider. If a user configures OpenRouter as their workspace provider, the orchestration path (used by `generation_runtime.handle_llm_generation`) will fail to resolve it. The `smart_deck_llm_service` path handles OpenRouter correctly via `_resolve_claude_config`.

2. **Three incompatible resolution chains:** Each call site resolves provider config differently. A workspace-configured OpenRouter key works in `smart_deck_llm_service` but not in `ai_orchestration/provider_resolver` or `smart_deck_source_enrichment_service`.

3. **Inconsistent retry:** Anthropic retries on 429/5xx; OpenAI and OpenRouter fail immediately. This means OpenAI/OpenRouter users may see transient failures that Anthropic users don't.
