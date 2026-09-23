from __future__ import annotations

from app.core.config import settings
from app.services.llm.dashscope_provider import call_dashscope_chat_completion, call_dashscope_multimodal_completion, extract_dashscope_text
from app.services.llm.anthropic_provider import call_anthropic_message, extract_anthropic_text
from app.services.llm.generation_service import _extract_json_payload
from app.services.llm.openai_provider import call_openai_response, extract_openai_text, extract_openai_usage
from app.services.llm.openrouter_provider import call_openrouter_chat_completion, extract_openrouter_text
from app.services.llm.operation_deadline import OperationDeadline
from app.services.llm.response_models import aggregate_usage
from app.services.llm.qwen_strategy import extract_token_usage


def call_structured_json(
    *,
    provider: str,
    model: str | None,
    api_key: str | None,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 90,
    max_tokens: int = 4000,
    image_urls: list[str] | None = None,
    credential_source: str = "environment",
    deadline: OperationDeadline | None = None,
    usage_sink: dict | None = None,
    json_schema: dict | None = None,
    schema_name: str = "structured_json_output",
) -> dict:
    if settings.is_production and provider != "openai" and credential_source != "workspace":
        # Smart Edit, Due Diligence, deck-map, market-research, and their
        # provider-backed repair calls all pass through this boundary. Explicit
        # encrypted workspace BYOK may use Qwen; shared Railway providers may not.
        raise ValueError("Production platform structured JSON operations require OpenAI.")
    if not model or not api_key:
        raise ValueError(f"{provider} requires a resolved model and API key.")
    provider_timeout = deadline.provider_timeout(float(timeout)) if deadline is not None else float(timeout)
    if provider == "anthropic":
        payload = call_anthropic_message(
            api_key=api_key,
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            user=user_prompt,
            timeout=provider_timeout,
        )
        aggregate_usage(usage_sink, payload.get("usage"))
        return _extract_json_payload(extract_anthropic_text(payload))
    if provider == "openai":
        response_format = (
            {"type": "json_schema", "name": schema_name, "schema": json_schema, "strict": False}
            if isinstance(json_schema, dict)
            else {"type": "json_object"}
        )
        payload = call_openai_response(
            api_key=api_key,
            model=model,
            system=system_prompt,
            user=user_prompt,
            timeout=provider_timeout,
            max_output_tokens=max_tokens,
            response_format=response_format,
            image_urls=image_urls,
        )
        if usage_sink is not None:
            aggregate_usage(usage_sink, extract_openai_usage(payload, model=model))
        return _extract_json_payload(extract_openai_text(payload))
    if provider == "openrouter":
        payload = call_openrouter_chat_completion(
            api_key=api_key,
            model=model,
            system=system_prompt,
            user=user_prompt,
            timeout=provider_timeout,
            response_format={"type": "json_object"},
        )
        aggregate_usage(usage_sink, payload.get("usage"))
        return _extract_json_payload(extract_openrouter_text(payload))
    if provider == "dashscope":
        if image_urls:
            # Vision tasks require OpenAI; Qwen vision model does not support PDF input
            response_format = (
                {"type": "json_schema", "name": schema_name, "schema": json_schema, "strict": False}
                if isinstance(json_schema, dict)
                else {"type": "json_object"}
            )
            payload = call_openai_response(
                api_key=settings.openai_api_key,
                model=settings.openai_vision_model,
                system=system_prompt,
                user=user_prompt,
                timeout=provider_timeout,
                max_output_tokens=max_tokens,
                response_format=response_format,
                image_urls=image_urls,
            )
            if usage_sink is not None:
                aggregate_usage(usage_sink, extract_openai_usage(payload, model=settings.openai_vision_model))
            return _extract_json_payload(extract_openai_text(payload))
        dashscope_model = model
        payload = call_dashscope_chat_completion(
            api_key=api_key,
            model=dashscope_model,
            system=system_prompt,
            user=user_prompt,
            timeout=provider_timeout,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        aggregate_usage(usage_sink, extract_token_usage(payload, model=dashscope_model, provider="dashscope").to_dict())
        return _extract_json_payload(extract_dashscope_text(payload))
    raise ValueError("A configured AI provider is required: Anthropic, OpenAI, OpenRouter, or DashScope.")
