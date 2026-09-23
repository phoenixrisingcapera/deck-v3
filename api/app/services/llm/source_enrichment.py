from __future__ import annotations

import json
import os
import re
from typing import Any

from app.core.config import settings
from app.services.llm import default_registry
from app.services.llm.response_models import LlmGenerationConfig
from app.services.rendering.schema_validation import validate_source_labels

JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def enrich_source_labels_with_llm(
    *,
    prompt_bundle: dict[str, str],
    slide_ids: set[str],
    block_ids: set[str],
) -> dict[str, Any]:
    """Call the configured provider for source labels, then validate before DB writes.

    The LLM never writes directly to the database. It returns JSON. This service
    parses and validates that JSON against known slide/block ids. The caller then
    persists only the normalized labels through SQLAlchemy models.
    """
    if not _source_llm_enrichment_enabled():
        return {"status": "disabled", "used": False, "validated": None, "provider": None, "model": None, "error": None}

    provider_config = _resolve_provider_config()
    provider = provider_config.get("provider")
    model = provider_config.get("model")
    api_key = provider_config.get("apiKey")
    if not provider or not model or not api_key:
        return {
            "status": "missing_provider",
            "used": False,
            "validated": None,
            "provider": provider,
            "model": model,
            "error": "No configured source-enrichment LLM provider key was available.",
        }

    try:
        text = _call_provider(provider=provider, model=model, api_key=api_key, prompt_bundle=prompt_bundle)
        parsed = _parse_json_response(text)
        validated = validate_source_labels(parsed, slide_ids=slide_ids, block_ids=block_ids)
        if not validated.get("ok"):
            return {
                "status": "invalid_llm_output",
                "used": False,
                "validated": validated,
                "provider": provider,
                "model": model,
                "error": "LLM output did not validate against known source ids.",
            }
        return {
            "status": "llm_enriched",
            "used": True,
            "validated": validated,
            "provider": provider,
            "model": model,
            "error": None,
        }
    except Exception as exc:
        return {
            "status": "llm_failed",
            "used": False,
            "validated": None,
            "provider": provider,
            "model": model,
            "error": f"{exc.__class__.__name__}: {exc}",
        }


def _source_llm_enrichment_enabled() -> bool:
    raw = os.getenv("SMART_DECK_SOURCE_LLM_ENRICHMENT_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _source_llm_max_tokens() -> int:
    raw = os.getenv("SMART_DECK_SOURCE_LLM_MAX_TOKENS", "2048").strip()
    try:
        return max(256, min(8192, int(raw)))
    except ValueError:
        return 2048


def _resolve_provider_config() -> dict[str, str | None]:
    mode = (settings.deck_generation_mode or "openai").strip().lower()
    if mode == "openai":
        return {"provider": "openai", "model": settings.openai_model, "apiKey": settings.openai_api_key or None}
    if mode in {"dashscope", "qwen", "alibaba"}:
        return {"provider": "dashscope", "model": settings.effective_qwen_model, "apiKey": settings.effective_qwen_api_key or None}

    # DISABLED FOR NOW: source-enrichment fallbacks to OpenAI / Anthropic / OpenRouter.
    # Re-enable these branches later if/when multi-provider product settings are
    # intentionally opened back up.
    # if mode in {"claude", "anthropic"}:
    #     return {"provider": "anthropic", "model": settings.anthropic_model, "apiKey": settings.anthropic_api_key or None}
    # if settings.openrouter_api_key:
    #     return {"provider": "openrouter", "model": settings.openrouter_model, "apiKey": settings.openrouter_api_key or None}
    return {"provider": "openai", "model": settings.openai_model, "apiKey": settings.openai_api_key or None}


def _call_provider(*, provider: str, model: str, api_key: str, prompt_bundle: dict[str, str]) -> str:
    system = prompt_bundle.get("system") or "Return valid JSON only."
    user = prompt_bundle.get("user") or "{}"
    max_tokens = _source_llm_max_tokens()
    config = LlmGenerationConfig(provider=provider, model=model, api_key=api_key, max_tokens=max_tokens)
    response = default_registry.get(provider).generate_text(system=system, user=user, config=config)
    return response.content


def _parse_json_response(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        candidate = candidate.removeprefix("json").strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = JSON_OBJECT_RE.search(candidate)
        if match is None:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("LLM response JSON root must be an object")
    return parsed
