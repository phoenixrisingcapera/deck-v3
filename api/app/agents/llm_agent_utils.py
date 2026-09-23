# Lets this file use modern type hints safely.
from __future__ import annotations

import json
from typing import Any

from app.core.config import settings
from app.services.llm import default_registry
from app.services.llm.response_models import LlmGenerationConfig, aggregate_usage
from app.services.llm.operation_deadline import OperationDeadline


__all__ = [
    "complete_json_with_ai_provider",
    "complete_json_with_provider",
    "extract_json_payload",
]


def extract_json_payload(raw_text: str) -> Any:
    """
    Take raw AI text and find the JSON inside it.

    Example input:
    ```json
    {"title": "Hello"}
    ```

    Example output:
    {"title": "Hello"}
    """

    # Remove spaces/newlines at the start and end.
    text = raw_text.strip()

    # If the AI wrapped the JSON in markdown code fences,
    # remove the ``` lines.
    if text.startswith("```"):
        lines = [
            line
            for line in text.splitlines()
            if not line.strip().startswith("```")
        ]
        text = "\n".join(lines).strip()

    # Find where a JSON object starts: {
    start_object = text.find("{")

    # Find where a JSON array starts: [
    start_array = text.find("[")

    # Keep only positions that actually exist.
    starts = [
        value
        for value in [start_object, start_array]
        if value != -1
    ]

    # If there is no { or [, there is no JSON.
    if not starts:
        raise ValueError("AI provider response did not contain JSON.")

    # Pick whichever starts first: { or [
    start = min(starts)

    # If JSON starts with {, find the last }.
    # If JSON starts with [, find the last ].
    end = text.rfind("}") if text[start] == "{" else text.rfind("]")

    # If there is no matching end, the JSON is broken.
    if end == -1 or end <= start:
        raise ValueError("AI provider response contained incomplete JSON.")

    # Convert the JSON text into real Python data.
    return json.loads(text[start : end + 1])


def complete_json_with_ai_provider(
    *,
    provider_config: dict | None,
    system: str,
    user: str,
    max_tokens: int = 1800,
    deadline: OperationDeadline | None = None,
    usage_sink: dict | None = None,
) -> Any | None:
    """Preferred provider-agnostic JSON completion entrypoint."""
    if not provider_config:
        return None

    api_key = provider_config.get("apiKey")
    provider = (provider_config.get("provider") or "").strip().lower()
    model = provider_config.get("model") or settings.anthropic_model
    if provider == "claude":
        provider = "anthropic"
    if provider == "qwen":
        provider = "dashscope"

    if provider not in {"anthropic", "openai", "openrouter", "dashscope"}:
        return None
    if not api_key or not model:
        return None

    timeout_seconds = deadline.provider_timeout(60.0) if deadline is not None else 60.0
    config = LlmGenerationConfig(provider=provider, model=model, api_key=api_key, max_tokens=max_tokens, timeout_seconds=timeout_seconds)
    response = default_registry.get(provider).generate_text(system=system, user=user, config=config)
    aggregate_usage(usage_sink, response.usage)
    return extract_json_payload(response.content)


def complete_json_with_provider(
    *,
    provider_config: dict | None,
    system: str,
    user: str,
    max_tokens: int = 1800,
    deadline: OperationDeadline | None = None,
    usage_sink: dict | None = None,
) -> Any | None:
    """Backward-compatible alias for `complete_json_with_ai_provider`."""
    return complete_json_with_ai_provider(
        provider_config=provider_config,
        system=system,
        user=user,
        max_tokens=max_tokens,
        deadline=deadline,
        usage_sink=usage_sink,
    )
