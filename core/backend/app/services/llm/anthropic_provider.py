from __future__ import annotations

"""Anthropic provider — low-level API transport and LLMProvider wrapper.

This module owns the raw HTTP transport to the Anthropic Messages API
(``call_anthropic_message``, ``extract_anthropic_text``) and the
``AnthropicProvider`` class that adapts those functions to the
application-wide ``LLMProvider`` protocol.

External callers should import the raw functions from here rather than
from the legacy ``app.ai.llm_provider`` path, which has been removed.
"""

import json
import logging
import time
from urllib import error as url_error
from urllib import request as url_request

from app.core.config import settings
from app.core.reliability import llm_circuit_breakers
from app.services.llm.provider_base import LLMProvider
from app.services.llm.response_models import LlmGenerationConfig, LlmResponse

logger = logging.getLogger(__name__)


ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION = "2023-06-01"
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}


def extract_anthropic_text(payload: dict) -> str:
    """Extract the first non-empty text block from an Anthropic Messages response.

    Raises ``ValueError`` if the payload is malformed or contains no text.
    """
    if not isinstance(payload, dict):
        raise ValueError("Anthropic response payload was not a mapping.")

    content = payload.get("content")
    if not isinstance(content, list):
        raise ValueError("Anthropic response did not include a text payload.")

    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                return text

    raise ValueError("Anthropic response did not include a text payload.")


def call_anthropic_message(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> dict:
    """Call the Anthropic Messages API with retry for transient failures.

    Retry is bounded by ``settings.anthropic_max_retries`` and spaced by
    ``settings.anthropic_retry_delay_seconds``.  Non-retryable HTTP statuses
    and JSON decode errors raise ``ValueError`` immediately.
    
    Protected by circuit breaker for production reliability.
    """
    return llm_circuit_breakers["anthropic"].call(
        _call_anthropic_message_impl,
        api_key=api_key,
        model=model,
        system=system,
        user=user,
        max_tokens=max_tokens,
        timeout=timeout,
        max_retries=max_retries,
    )


def _call_anthropic_message_impl(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int | None = None,
    timeout: int | None = None,
    max_retries: int | None = None,
) -> dict:
    """Internal implementation of Anthropic API call with retry logic."""
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is required for Claude generation.")
    if not model:
        raise ValueError("Anthropic model is required for message generation.")

    token_limit = max(1, int(max_tokens or settings.anthropic_max_tokens))

    request_payload = {
        "model": model,
        "max_tokens": token_limit,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    request_body = json.dumps(request_payload, ensure_ascii=False).encode("utf-8")
    effective_timeout = _effective_timeout(timeout)
    attempts = (settings.anthropic_max_retries if max_retries is None else max_retries) + 1

    logger.info(
        "Anthropic API call initiated",
        extra={
            "provider": "anthropic",
            "model": model,
            "max_tokens": token_limit,
            "timeout": effective_timeout,
            "attempts": attempts,
        }
    )

    last_error: Exception | None = None
    for attempt in range(attempts):
        request = url_request.Request(
            url=ANTHROPIC_MESSAGES_URL,
            data=request_body,
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
            },
            method="POST",
        )
        try:
            with url_request.urlopen(request, timeout=effective_timeout) as response:
                raw = response.read()
                result = json.loads(raw.decode("utf-8"))
                logger.info(
                    "Anthropic API call successful",
                    extra={
                        "provider": "anthropic",
                        "model": model,
                            "status_code": getattr(response, "status", None),
                        "attempt": attempt + 1,
                    }
                )
                return result
        except url_error.HTTPError as exc:
            last_error = exc
            logger.warning(
                "Anthropic API call failed with HTTP error",
                extra={
                    "provider": "anthropic",
                    "model": model,
                    "status_code": exc.code,
                    "attempt": attempt + 1,
                    "error": str(exc),
                }
            )
            if exc.code not in RETRYABLE_HTTP_STATUSES or attempt >= attempts - 1:
                raise ValueError(f"Anthropic generation failed with status {exc.code}") from exc
            _sleep_before_retry()
        except url_error.URLError as exc:
            last_error = exc
            logger.warning(
                "Anthropic API call failed with network error",
                extra={
                    "provider": "anthropic",
                    "model": model,
                    "attempt": attempt + 1,
                    "error": str(exc),
                }
            )
            if attempt >= attempts - 1:
                raise ValueError("Anthropic generation failed due to a network error") from exc
            _sleep_before_retry()
        except json.JSONDecodeError as exc:
            logger.error(
                "Anthropic API returned invalid JSON",
                extra={
                    "provider": "anthropic",
                    "model": model,
                    "error": str(exc),
                }
            )
            raise ValueError("Anthropic generation returned invalid JSON") from exc

    raise ValueError("Anthropic generation failed") from last_error


def _safe_error_text(error: Exception) -> str:
    """Return a truncated safe representation of an HTTP or URL error."""
    if isinstance(error, url_error.HTTPError):
        try:
            body = error.read().decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        if body:
            return body[:400]
        return ""
    if isinstance(error, url_error.URLError):
        reason = str(getattr(error, "reason", ""))
        return reason[:400]
    return ""


def _effective_timeout(requested_timeout: int | None) -> int:
    """Clamp *requested_timeout* to the configured maximum."""
    configured_timeout = max(1, settings.anthropic_timeout_seconds)
    if requested_timeout is None:
        return configured_timeout
    return max(1, min(int(requested_timeout), configured_timeout))


def _sleep_before_retry() -> None:
    """Sleep for the configured retry delay, if non-zero."""
    delay = float(settings.anthropic_retry_delay_seconds)
    if delay > 0:
        time.sleep(delay)


class AnthropicProvider(LLMProvider):
    """LLMProvider implementation backed by Anthropic's Messages API."""

    def __init__(self) -> None:
        self._provider_name = "anthropic"

    @property
    def name(self) -> str:
        return self._provider_name

    def generate_text(self, *, system: str | None = None, user: str, config: LlmGenerationConfig) -> LlmResponse:
        """Send a prompt to Anthropic and return the parsed response."""
        api_key = config.api_key
        if not api_key:
            raise ValueError("Anthropic API key is required")

        raw = call_anthropic_message(
            api_key=api_key,
            model=config.model,
            system=system or "",
            user=user,
            max_tokens=config.max_tokens,
            timeout=config.timeout_seconds,
        )
        text = extract_anthropic_text(raw)
        return LlmResponse(content=text, model=config.model, provider=self._provider_name, usage=raw.get("usage"), raw=raw)

    def validate_connection(self, *, api_key: str, model: str | None = None) -> bool:
        """Verify the provider credentials by issuing a minimal API call."""
        try:
            call_anthropic_message(api_key=api_key, model=model or "claude-sonnet-4-20250514", system="Say OK", user="OK", max_tokens=10, timeout=10)
            return True
        except Exception:
            return False
