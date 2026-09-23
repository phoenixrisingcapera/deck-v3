from __future__ import annotations

"""OpenRouter provider — low-level API transport and LLMProvider wrapper.

This module owns the raw HTTP transport to the OpenRouter chat completions
endpoint (``call_openrouter_chat_completion``, ``extract_openrouter_text``)
and the ``OpenRouterProvider`` class that adapts those functions to the
application-wide ``LLMProvider`` protocol.

External callers should import the raw functions from here rather than
from the legacy ``app.ai.openrouter_provider`` path, which has been removed.
"""

import json
import logging
from urllib import error as url_error
from urllib import request as url_request

from app.core.config import settings
from app.core.reliability import llm_circuit_breakers, llm_retry_policies, with_reliability
from app.services.llm.provider_base import LLMProvider
from app.services.llm.response_models import LlmGenerationConfig, LlmResponse

logger = logging.getLogger(__name__)


OPENROUTER_CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"


def extract_openrouter_text(payload: dict) -> str:
    """Extract text from an OpenRouter chat completions response.

    Handles both plain-string and structured-content message formats.
    """
    for choice in payload.get("choices", []):
        message = choice.get("message") if isinstance(choice, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            text = "".join(
                block.get("text", "")
                for block in content
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ).strip()
            if text:
                return text
    raise ValueError("OpenRouter response did not include a text payload.")


@with_reliability(
    circuit_breaker=llm_circuit_breakers["openrouter"],
    retry_policy=llm_retry_policies["openrouter"],
)
def call_openrouter_chat_completion(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout: int | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
    idempotency_key: str | None = None,
) -> dict:
    """Call the OpenRouter chat completions API and return parsed JSON.

    Sends ``HTTP-Referer`` and ``X-Title`` headers when configured.
    HTTP/transport errors raise a sanitized ``ValueError`` without provider response bodies.
    
    Protected by circuit breaker and retry logic for production reliability.
    """
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is required for OpenRouter generation.")

    logger.info(
        "OpenRouter API call initiated",
        extra={
            "provider": "openrouter",
            "model": model,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
    )

    request_payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if max_tokens is not None:
        request_payload["max_tokens"] = max(1, max_tokens)
    if response_format is not None:
        request_payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if settings.openrouter_site_url:
        headers["HTTP-Referer"] = settings.openrouter_site_url
    if settings.openrouter_app_name:
        headers["X-Title"] = settings.openrouter_app_name
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    http_request = url_request.Request(
        url=OPENROUTER_CHAT_COMPLETIONS_URL,
        data=json.dumps(request_payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with url_request.urlopen(http_request, timeout=_effective_timeout(timeout)) as response:
            result = json.loads(response.read().decode("utf-8"))
            logger.info(
                "OpenRouter API call successful",
                extra={
                    "provider": "openrouter",
                    "model": model,
                    "status_code": response.status,
                }
            )
            return result
    except url_error.HTTPError as exc:
        exc.read()
        logger.error(
            "OpenRouter API call failed with HTTP error",
            extra={
                "provider": "openrouter",
                "model": model,
                "status_code": exc.code,
            }
        )
        raise ValueError(f"OpenRouter generation failed with status {exc.code}") from exc
    except url_error.URLError as exc:
        logger.error(
            "OpenRouter API call failed with network error",
            extra={
                "provider": "openrouter",
                "model": model,
                "error": str(exc),
            }
        )
        raise ValueError("OpenRouter generation failed due to a network error") from exc


def _effective_timeout(requested_timeout: int | None) -> int:
    """Clamp *requested_timeout* to the configured maximum."""
    configured_timeout = max(1, settings.openrouter_timeout_seconds)
    if requested_timeout is None:
        return configured_timeout
    return max(1, min(requested_timeout, configured_timeout))


class OpenRouterProvider(LLMProvider):
    """LLMProvider implementation backed by OpenRouter's chat completions API."""

    def __init__(self) -> None:
        self._provider_name = "openrouter"

    @property
    def name(self) -> str:
        return self._provider_name

    def generate_text(self, *, system: str | None = None, user: str, config: LlmGenerationConfig) -> LlmResponse:
        """Send a prompt to OpenRouter and return the parsed response."""
        api_key = config.api_key
        if not api_key:
            raise ValueError("OpenRouter API key is required")

        raw = call_openrouter_chat_completion(
            api_key=api_key,
            model=config.model,
            system=system or "",
            user=user,
            timeout=config.timeout_seconds,
            max_tokens=config.max_tokens,
            response_format=config.extra.get("response_format") if config.extra else None,
        )
        text = extract_openrouter_text(raw)
        return LlmResponse(content=text, model=config.model, provider=self._provider_name, usage=raw.get("usage"), raw=raw)

    def validate_connection(self, *, api_key: str, model: str | None = None) -> bool:
        """Verify the provider credentials by issuing a minimal API call."""
        try:
            call_openrouter_chat_completion(api_key=api_key, model=model or "openai/gpt-4o", system="Say OK", user="OK", timeout=10)
            return True
        except Exception:
            return False
