from __future__ import annotations

"""DashScope (Alibaba Qwen) provider — low-level API transport and LLMProvider wrapper.

DashScope exposes an OpenAI-compatible chat completions endpoint.  This module
provides raw HTTP transport (``call_dashscope_chat_completion``,
``call_dashscope_embedding``, ``extract_dashscope_text``) and the
``DashScopeProvider`` class that adapts those functions to the application-wide
``LLMProvider`` protocol.

Endpoints (OpenAI-compatible):
  Chat:   ``{base_url}/chat/completions``
  Embed:  ``{base_url}/embeddings``

International base URL:  ``https://dashscope-intl.aliyuncs.com/compatible-mode/v1``
China base URL:           ``https://dashscope.aliyuncs.com/compatible-mode/v1``
"""

import json
import logging
import socket
import time
from contextvars import ContextVar
from urllib import error as url_error
from urllib import request as url_request

from app.core.config import settings
from app.core.reliability import llm_circuit_breakers
from app.services.llm.provider_base import LLMProvider
from app.services.llm.response_models import LlmGenerationConfig, LlmResponse
from app.services.llm.qwen_strategy import extract_token_usage, is_retryable_error

logger = logging.getLogger(__name__)

_last_usage = None
_last_error_category = None
_last_success_at = None
_tracked_usage: ContextVar[dict[str, int] | None] = ContextVar("dashscope_tracked_usage", default=None)


def get_last_usage() -> dict | None:
    return _last_usage.to_dict() if _last_usage else None


def begin_usage_tracking() -> None:
    """Start request-local aggregation so concurrent jobs cannot share counts."""
    _tracked_usage.set({"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})


def get_tracked_usage() -> dict[str, int] | None:
    usage = _tracked_usage.get()
    return dict(usage) if usage is not None else None


def get_last_error_category() -> str | None:
    return _last_error_category


def get_last_success_at() -> str | None:
    return _last_success_at.isoformat() if _last_success_at else None


def _base_url() -> str:
    return (settings.dashscope_base_url or "").rstrip("/")


def _chat_url() -> str:
    return f"{_base_url()}/chat/completions"


def _embedding_url() -> str:
    return f"{_base_url()}/embeddings"


def _models_url() -> str:
    return f"{_base_url()}/models"


def discover_dashscope_model_ids(*, api_key: str, timeout: int = 10) -> set[str]:
    """Return provider-advertised model IDs without exposing response details."""
    http_request = url_request.Request(
        url=_models_url(),
        headers=_dashscope_headers(api_key),
        method="GET",
    )
    try:
        with url_request.urlopen(http_request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except url_error.HTTPError as exc:
        exc.read()
        raise ValueError(f"DashScope model discovery failed with status {exc.code}") from exc
    except (url_error.URLError, TimeoutError, socket.timeout) as exc:
        raise ValueError("DashScope model discovery failed due to a network error") from exc
    models = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        raise ValueError("DashScope model discovery returned an invalid response")
    return {
        str(model["id"])
        for model in models
        if isinstance(model, dict) and isinstance(model.get("id"), str) and model["id"]
    }


def extract_dashscope_text(payload: dict) -> str:
    """Extract text from a DashScope chat completions response."""
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
    raise ValueError("DashScope response did not include a text payload.")


def _dashscope_headers(api_key: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if settings.dashscope_workspace_id:
        headers["X-DashScope-WorkSpace"] = settings.dashscope_workspace_id
    return headers


def _classify_error(exc: Exception) -> str:
    if isinstance(exc, url_error.HTTPError):
        code = exc.code
        if code == 401 or code == 403:
            return "authentication"
        if code == 429:
            return "rate_limit"
        if code >= 500:
            return "server_error"
        return f"http_{code}"
    if isinstance(exc, url_error.URLError):
        return "network"
    return "unknown"


def _dashscope_request(url: str, payload: dict, api_key: str, timeout: int, *, operation: str = "chat", max_retries: int | None = None) -> dict:
    global _last_usage, _last_error_category, _last_success_at

    retries = max_retries if max_retries is not None else settings.qwen_max_retries
    last_exc = None

    for attempt in range(retries + 1):
        http_request = url_request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=_dashscope_headers(api_key),
            method="POST",
        )
        started = time.perf_counter()
        try:
            with url_request.urlopen(http_request, timeout=timeout) as response:
                raw = json.loads(response.read().decode("utf-8"))
                latency_ms = round((time.perf_counter() - started) * 1000, 2)
                _last_usage = extract_token_usage(
                    raw,
                    model=payload.get("model"),
                    provider="dashscope",
                    operation=operation,
                    latency_ms=latency_ms,
                    retry_count=attempt,
                )
                tracked_usage = _tracked_usage.get()
                if tracked_usage is not None:
                    tracked_usage["input_tokens"] += int(_last_usage.input_tokens or 0)
                    tracked_usage["output_tokens"] += int(_last_usage.output_tokens or 0)
                    tracked_usage["total_tokens"] += int(_last_usage.total_tokens or 0)
                _last_error_category = None
                _last_success_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                return raw
        except url_error.HTTPError as exc:
            last_exc = exc
            _last_error_category = _classify_error(exc)
            exc.read()
            if not is_retryable_error(exc):
                raise ValueError(f"DashScope request failed with status {exc.code}") from exc
            if attempt < retries:
                delay = 0.5 * (2 ** attempt)
                logger.warning("dashscope_retryable_error", extra={"attempt": attempt + 1, "status": exc.code, "delay_s": delay})
                time.sleep(delay)
                continue
            raise ValueError(f"DashScope request failed with status {exc.code}") from exc
        except url_error.URLError as exc:
            last_exc = exc
            _last_error_category = "network"
            if attempt < retries:
                delay = 0.5 * (2 ** attempt)
                logger.warning("dashscope_network_retry", extra={"attempt": attempt + 1, "delay_s": delay})
                time.sleep(delay)
                continue
            raise ValueError("DashScope request failed due to a network error") from exc
        except (TimeoutError, socket.timeout) as exc:
            last_exc = exc
            _last_error_category = "timeout"
            if attempt < retries:
                delay = 0.5 * (2 ** attempt)
                logger.warning("dashscope_timeout_retry", extra={"attempt": attempt + 1, "delay_s": delay})
                time.sleep(delay)
                continue
            raise ValueError("DashScope request timed out after retrying") from exc

    raise ValueError("DashScope request failed after all retries")


def call_dashscope_chat_completion(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout: int | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
    temperature: float | None = None,
    max_retries: int | None = None,
) -> dict:
    """Call the DashScope (Alibaba Qwen) chat completions API.
    
    Protected by circuit breaker for production reliability.
    """
    return llm_circuit_breakers["dashscope"].call(
        _call_dashscope_chat_completion_impl,
        api_key=api_key,
        model=model,
        system=system,
        user=user,
        timeout=timeout,
        max_tokens=max_tokens,
        response_format=response_format,
        temperature=temperature,
        max_retries=max_retries,
    )


def call_dashscope_multimodal_completion(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    image_urls: list[str],
    timeout: int | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
    temperature: float | None = None,
) -> dict:
    return llm_circuit_breakers["dashscope"].call(
        _call_dashscope_multimodal_completion_impl,
        api_key=api_key,
        model=model,
        system=system,
        user=user,
        image_urls=image_urls,
        timeout=timeout,
        max_tokens=max_tokens,
        response_format=response_format,
        temperature=temperature,
    )


def _call_dashscope_chat_completion_impl(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout: int | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
    temperature: float | None = None,
    max_retries: int | None = None,
) -> dict:
    """Internal implementation of DashScope chat completion."""
    if not api_key:
        raise ValueError("QWEN_API_KEY is required for Qwen generation.")

    logger.info(
        "DashScope API call initiated",
        extra={
            "provider": "dashscope",
            "model": model,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
    )

    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if max_tokens is not None:
        payload["max_tokens"] = max(1, max_tokens)
    if response_format is not None:
        payload["response_format"] = response_format
    if temperature is not None:
        payload["temperature"] = max(0.0, min(temperature, 2.0))

    result = _dashscope_request(_chat_url(), payload, api_key, _effective_timeout(timeout), operation="chat", max_retries=max_retries)
    
    logger.info(
        "DashScope API call successful",
        extra={
            "provider": "dashscope",
            "model": model,
        }
    )
    
    return result


def _call_dashscope_multimodal_completion_impl(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    image_urls: list[str],
    timeout: int | None = None,
    max_tokens: int | None = None,
    response_format: dict | None = None,
    temperature: float | None = None,
) -> dict:
    if not api_key:
        raise ValueError("QWEN_API_KEY is required for Qwen vision generation.")
    if not image_urls:
        raise ValueError("DashScope multimodal completion requires at least one image URL.")

    content = [{"type": "text", "text": user}]
    content.extend({"type": "image_url", "image_url": {"url": url}} for url in image_urls)
    payload: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
    }
    if max_tokens is not None:
        payload["max_tokens"] = max(1, max_tokens)
    if response_format is not None:
        payload["response_format"] = response_format
    if temperature is not None:
        payload["temperature"] = max(0.0, min(temperature, 2.0))
    return _dashscope_request(_chat_url(), payload, api_key, _effective_timeout(timeout), operation="vision")


def call_dashscope_embedding(
    *,
    api_key: str,
    model: str,
    input: list[str],
    dimensions: int | None = None,
    timeout: int | None = None,
) -> dict:
    """Call the DashScope (Alibaba) embeddings API (OpenAI-compatible)."""
    if not api_key:
        raise ValueError("QWEN_API_KEY is required for Qwen embeddings.")

    payload: dict = {
        "model": model,
        "input": input,
    }
    if dimensions is not None:
        payload["dimensions"] = dimensions

    return _dashscope_request(_embedding_url(), payload, api_key, _effective_timeout(timeout), operation="embedding", max_retries=1)


def _effective_timeout(requested_timeout: int | None) -> int:
    configured_timeout = max(1, settings.effective_qwen_timeout)
    if requested_timeout is None:
        return configured_timeout
    return max(1, min(requested_timeout, configured_timeout))


class DashScopeProvider(LLMProvider):
    """LLMProvider implementation backed by Alibaba DashScope (Qwen) chat completions API."""

    def __init__(self) -> None:
        self._provider_name = "dashscope"

    @property
    def name(self) -> str:
        return self._provider_name

    def generate_text(self, *, system: str | None = None, user: str, config: LlmGenerationConfig) -> LlmResponse:
        """Send a prompt to DashScope and return the parsed response."""
        api_key = config.api_key
        if not api_key:
            raise ValueError("Qwen API key is required")

        raw = call_dashscope_chat_completion(
            api_key=api_key,
            model=config.model,
            system=system or "",
            user=user,
            timeout=config.timeout_seconds,
            max_tokens=config.max_tokens,
            response_format=config.extra.get("response_format") if config.extra else None,
            temperature=settings.qwen_temperature,
        )
        text = extract_dashscope_text(raw)
        usage = extract_token_usage(raw, model=config.model, provider=self._provider_name).to_dict()
        return LlmResponse(content=text, model=config.model, provider=self._provider_name, usage=usage, raw=raw)

    def validate_connection(self, *, api_key: str, model: str | None = None) -> bool:
        """Verify the provider credentials by issuing a minimal API call."""
        try:
            call_dashscope_chat_completion(api_key=api_key, model=model or "qwen-flash", system="Say OK", user="OK", timeout=10)
            return True
        except Exception:
            return False
