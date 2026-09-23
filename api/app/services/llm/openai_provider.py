from __future__ import annotations

"""OpenAI Responses API provider — low-level transport and LLMProvider wrapper.

This module owns the raw HTTP transport to the OpenAI Responses API
(``call_openai_response``, ``extract_openai_text``), the status-aware typed
response parser (``parse_openai_structured_response``), and the
``OpenAIProvider`` class that adapts those functions to the application-wide
``LLMProvider`` protocol.

External callers should import the raw functions from here rather than
from the legacy ``app.ai.openai_provider`` path, which has been removed.
"""

import json
import logging
import hmac
import re
from http.client import IncompleteRead
import os
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib import error as url_error
from urllib import request as url_request

from app.core.config import settings
from app.core.reliability import llm_circuit_breakers, llm_retry_policies, with_reliability
from app.services.llm.provider_base import LLMProvider
from app.services.llm.response_models import LlmGenerationConfig, LlmResponse

logger = logging.getLogger(__name__)


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
_model_access_cache: dict[tuple[str, str], tuple[float, dict[str, object]]] = {}
_model_access_cache_lock = threading.Lock()
_MODEL_ACCESS_CACHE_MAX_ENTRIES = 32
_MODEL_ACCESS_CACHE_TTL_SECONDS = 300.0
_MODEL_ACCESS_CACHE_HMAC_KEY = os.urandom(32)
_INSTANT_ATTESTATION_HMAC_KEY = os.urandom(32)
_INSTANT_ATTESTATION_FRESH_SECONDS = 300.0
_INSTANT_ATTESTATION_REFRESH_SECONDS = 240.0
_INSTANT_ATTESTATION_BACKOFF_SECONDS = 30.0
_INSTANT_ATTESTATION_MAX_BACKOFF_SECONDS = 300.0
_OPENAI_RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}
_OPENAI_ACTION_REQUIRED_CODES = {
    "credit_balance_exhausted",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
    "organization_usage_limit_exceeded",
    "insufficient_quota",
    "authentication_error",
    "permission_denied",
    "model_not_found",
}
_RATE_LIMIT_HEADER_NAMES = (
    "x-ratelimit-remaining-requests",
    "x-ratelimit-reset-requests",
    "x-ratelimit-remaining-tokens",
    "x-ratelimit-reset-tokens",
    "x-ratelimit-remaining-project-tokens",
    "x-ratelimit-reset-project-tokens",
)


@dataclass(frozen=True)
class _InstantModelAccessAttestation:
    credential_hmac: bytes
    model: str
    verified_at: datetime
    verified_monotonic: float
    process_id: int


_instant_attestation: _InstantModelAccessAttestation | None = None
_instant_attestation_next_refresh_at = 0.0
_instant_attestation_failure_count = 0
_instant_attestation_lock = threading.Lock()


def _instant_attestation_error_category(exc: BaseException) -> tuple[str, str]:
    """Return fixed probe-failure labels without reflecting exception text."""
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):
        return "malformed_response", "ResponseParseError"
    if isinstance(exc, (url_error.URLError, TimeoutError, socket.timeout)):
        return "transport_error", "ProviderTransportError"
    if isinstance(exc, (AttributeError, KeyError, TypeError, ValueError)):
        return "invalid_response", "ResponseShapeError"
    return "unexpected_error", "UnexpectedProbeError"


def _mark_instant_attestation_failed(*, now_monotonic: float) -> None:
    """Clear readiness and advance the process-local bounded retry backoff."""
    global _instant_attestation
    global _instant_attestation_failure_count
    global _instant_attestation_next_refresh_at

    _instant_attestation = None
    _instant_attestation_failure_count += 1
    delay = min(
        _INSTANT_ATTESTATION_MAX_BACKOFF_SECONDS,
        _INSTANT_ATTESTATION_BACKOFF_SECONDS
        * (2 ** min(_instant_attestation_failure_count - 1, 16)),
    )
    _instant_attestation_next_refresh_at = now_monotonic + delay


def fail_instant_openai_model_access_attestation(exc: BaseException) -> bool:
    """Fail closed when lifecycle code itself encounters an unexpected error."""
    now = time.monotonic()
    with _instant_attestation_lock:
        _mark_instant_attestation_failed(now_monotonic=now)
    category, safe_class = _instant_attestation_error_category(exc)
    logger.warning(
        "instant_openai_attestation_refresh_failed",
        extra={"error_category": category, "error_class": safe_class},
    )
    return False


def _credential_hmac(api_key: str, *, key: bytes) -> bytes:
    return hmac.digest(key, api_key.encode("utf-8"), "sha256")


def instant_openai_model_access_attested(
    *, api_key: str, model: str, now_monotonic: float | None = None
) -> bool:
    """Return private process-local readiness for the current credential/model."""
    now = time.monotonic() if now_monotonic is None else now_monotonic
    global _instant_attestation
    global _instant_attestation_failure_count
    global _instant_attestation_next_refresh_at
    with _instant_attestation_lock:
        attestation = _instant_attestation
        if attestation is None or not api_key:
            return False
        identity_matches = (
            attestation.process_id == os.getpid()
            and attestation.model == model
            and hmac.compare_digest(
                attestation.credential_hmac,
                _credential_hmac(api_key, key=_INSTANT_ATTESTATION_HMAC_KEY),
            )
        )
        if not identity_matches:
            _instant_attestation = None
            _instant_attestation_failure_count = 0
            _instant_attestation_next_refresh_at = 0.0
            return False
        if now < attestation.verified_monotonic:
            _instant_attestation = None
            _instant_attestation_next_refresh_at = 0.0
            return False
        return now - attestation.verified_monotonic <= _INSTANT_ATTESTATION_FRESH_SECONDS


def _instant_attestation_matches_unlocked(*, api_key: str, model: str, now: float) -> bool:
    attestation = _instant_attestation
    return bool(
        attestation is not None
        and api_key
        and attestation.process_id == os.getpid()
        and attestation.model == model
        and now >= attestation.verified_monotonic
        and now - attestation.verified_monotonic <= _INSTANT_ATTESTATION_FRESH_SECONDS
        and hmac.compare_digest(
            attestation.credential_hmac,
            _credential_hmac(api_key, key=_INSTANT_ATTESTATION_HMAC_KEY),
        )
    )


def refresh_instant_openai_model_access_attestation(
    *, api_key: str, model: str, force: bool = False, now_monotonic: float | None = None
) -> bool:
    """Refresh one private process-local attestation with one passive model GET."""
    from app.core.openai_full_html_policy import FULL_HTML_OPENAI_MODEL

    global _instant_attestation
    global _instant_attestation_failure_count
    global _instant_attestation_next_refresh_at

    now = time.monotonic() if now_monotonic is None else now_monotonic
    with _instant_attestation_lock:
        current = _instant_attestation
        if current is not None and (
            current.process_id != os.getpid()
            or current.model != model
            or not api_key
            or not hmac.compare_digest(
                current.credential_hmac,
                _credential_hmac(api_key, key=_INSTANT_ATTESTATION_HMAC_KEY),
            )
        ):
            _instant_attestation = None
            _instant_attestation_failure_count = 0
            _instant_attestation_next_refresh_at = 0.0
        if not force and now < _instant_attestation_next_refresh_at:
            return _instant_attestation_matches_unlocked(api_key=api_key, model=model, now=now)
        if not api_key or model != FULL_HTML_OPENAI_MODEL:
            _instant_attestation = None
            _instant_attestation_next_refresh_at = now + _INSTANT_ATTESTATION_BACKOFF_SECONDS
            return False
        try:
            result = check_openai_model_access(
                api_key=api_key, model=model, force_refresh=True
            )
            verified = result.get("verified") is True and result.get("model") == model
        except Exception as exc:
            _mark_instant_attestation_failed(now_monotonic=now)
            category, safe_class = _instant_attestation_error_category(exc)
            logger.warning(
                "instant_openai_attestation_refresh_failed",
                extra={"error_category": category, "error_class": safe_class},
            )
            return False
        if verified:
            _instant_attestation = _InstantModelAccessAttestation(
                credential_hmac=_credential_hmac(api_key, key=_INSTANT_ATTESTATION_HMAC_KEY),
                model=model,
                verified_at=datetime.now(timezone.utc),
                verified_monotonic=now,
                process_id=os.getpid(),
            )
            _instant_attestation_failure_count = 0
            _instant_attestation_next_refresh_at = now + _INSTANT_ATTESTATION_REFRESH_SECONDS
            return True
        _mark_instant_attestation_failed(now_monotonic=now)
        return False


def _reset_instant_openai_model_access_attestation() -> None:
    """Reset process-local lifecycle state for isolated tests only."""
    global _instant_attestation
    global _instant_attestation_failure_count
    global _instant_attestation_next_refresh_at
    with _instant_attestation_lock:
        _instant_attestation = None
        _instant_attestation_failure_count = 0
        _instant_attestation_next_refresh_at = 0.0


def _redacted_provider_code(value: object, *, default: str = "unknown") -> str:
    if not isinstance(value, str):
        return default
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 120:
        return default
    if any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for character in normalized):
        return default
    return normalized


class OpenAIHttpError(Exception):
    """Redacted OpenAI HTTP failure safe for job persistence and logs."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        retryable: bool,
        provider_request_id: str | None = None,
        client_request_id: str | None = None,
        retry_after_seconds: float | None = None,
        rate_limit_metadata: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.retryable = retryable
        self.provider_request_id = provider_request_id
        self.client_request_id = client_request_id
        self.retry_after_seconds = retry_after_seconds
        self.rate_limit_metadata = rate_limit_metadata or {}
        super().__init__(f"OpenAI request failed ({code})")


class OpenAITransportError(Exception):
    """Redacted retryable OpenAI network or timeout failure."""

    code = "provider_network_error"
    retryable = True

    def __init__(self, *, client_request_id: str | None = None) -> None:
        self.client_request_id = client_request_id
        super().__init__("OpenAI request failed (provider_network_error)")


class OpenAIResponseIncomplete(Exception):
    """The response ended before completion (e.g. max_output_tokens, content_filter).

    The extracted output is partial and must not be fed into schema validation
    or repair. Max-token truncation is retryable once by the slide caller. Other
    reasons are final, and durable jobs always fail closed instead of replaying
    the whole deck.
    """

    code = "openai_response_incomplete"
    retryable = False

    def __init__(self, *, reason: str | None = None, model: str | None = None, response_id: str | None = None) -> None:
        self.reason = _redacted_provider_code(reason)
        self.retryable = self.reason == "max_output_tokens"
        self.model = model
        self.response_id = response_id
        super().__init__(f"OpenAI response incomplete ({self.reason})")


class OpenAIResponseRefusal(Exception):
    """The model refused the request; retrying the identical prompt is not productive."""

    code = "openai_response_refusal"
    retryable = False

    def __init__(self, *, model: str | None = None, response_id: str | None = None) -> None:
        self.model = model
        self.response_id = response_id
        super().__init__("OpenAI response refused the request")


class OpenAIResponseFailed(Exception):
    """The provider reported a failed response with a redacted reason code."""

    code = "openai_response_failed"
    retryable = False

    def __init__(self, *, reason: str | None = None, model: str | None = None, response_id: str | None = None) -> None:
        self.reason = _redacted_provider_code(reason)
        self.provider_error_code = self.reason
        self.retryable = self.reason == "server_error"
        self.model = model
        self.response_id = response_id
        super().__init__(f"OpenAI response failed ({self.reason})")


class OpenAIResponseMalformed(ValueError):
    """The response completed but did not contain usable text output.

    Extends ``ValueError`` for backward compatibility with callers that
    catch ``ValueError`` from ``extract_openai_text``.
    """

    code = "openai_response_malformed"
    retryable = False

    def __init__(self, *, reason: str | None = None, model: str | None = None, response_id: str | None = None) -> None:
        self.reason = _redacted_provider_code(reason, default="no_text_output")
        self.model = model
        self.response_id = response_id
        super().__init__(f"OpenAI response malformed ({self.reason})")


def _openai_error_code(exc: url_error.HTTPError) -> str:
    try:
        raw = exc.read()
        payload = json.loads(raw.decode("utf-8")) if raw else {}
        provider_code = ((payload.get("error") or {}).get("code") or "").strip().lower()
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
        provider_code = ""
    if provider_code:
        return _redacted_provider_code(provider_code)
    if exc.code == 401:
        return "authentication_error"
    if exc.code == 403:
        return "permission_denied"
    if exc.code == 404:
        return "model_not_found"
    if exc.code in {400, 409, 422}:
        return "invalid_request"
    if exc.code == 429:
        return "rate_limit_exceeded"
    if exc.code in _OPENAI_RETRYABLE_HTTP_STATUSES:
        return "provider_server_error"
    return "provider_http_error"


def _retry_after_seconds(headers: object) -> float | None:
    value = getattr(headers, "get", lambda _name: None)("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(str(value).strip()))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(str(value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def _safe_response_metadata(headers: object, *, client_request_id: str | None = None) -> dict[str, object]:
    getter = getattr(headers, "get", lambda _name: None)
    rate = {
        name: str(value)[:120]
        for name in _RATE_LIMIT_HEADER_NAMES
        if (value := getter(name)) is not None
    }
    return {
        "provider_request_id": str(getter("x-request-id") or "")[:255] or None,
        "client_request_id": client_request_id,
        "retry_after_seconds": _retry_after_seconds(headers),
        "rate_limit_metadata": rate,
    }


def _is_retryable_openai_error(exc: Exception) -> bool:
    if isinstance(exc, OpenAIHttpError):
        return exc.retryable
    if isinstance(exc, OpenAITransportError):
        return exc.retryable
    return isinstance(exc, (OpenAITransportError, url_error.URLError, TimeoutError, socket.timeout))


def _counts_as_openai_circuit_failure(exc: Exception) -> bool:
    if isinstance(exc, OpenAIHttpError):
        return exc.retryable and exc.code != "rate_limit_exceeded"
    return isinstance(exc, OpenAITransportError)


def _openai_retry_policy():
    """Build the OpenAI retry policy without mutating import-time globals."""
    policy = llm_retry_policies["openai"]
    return type(policy)(
        max_attempts=policy.max_attempts,
        base_delay=policy.base_delay,
        max_delay=policy.max_delay,
        exponential_base=policy.exponential_base,
        jitter=policy.jitter,
        retryable_exceptions=policy.retryable_exceptions,
        retry_predicate=_is_retryable_openai_error,
    )

_MODEL_COST_PER_1K_TOKENS_USD: dict[str, tuple[Decimal, Decimal]] = {
    "gpt-4.1": (Decimal("0.002"), Decimal("0.008")),
    "gpt-4.1-mini": (Decimal("0.0004"), Decimal("0.0016")),
    "gpt-4o": (Decimal("0.005"), Decimal("0.015")),
    "gpt-5": (Decimal("0.00125"), Decimal("0.010")),
    "gpt-5-2025-08-07": (Decimal("0.00125"), Decimal("0.010")),
    "text-embedding-3-small": (Decimal("0.00002"), Decimal("0")),
    "text-embedding-3-large": (Decimal("0.00013"), Decimal("0")),
}


def extract_openai_text(payload: dict) -> str:
    """Extract text from an OpenAI Responses API payload (legacy-compatible).

    Public behavior is unchanged: returns the joined assistant text or raises a
    generic ``ValueError`` when the payload contains no usable text. Callers
    that need typed response-state classification (incomplete / refusal /
    failed / malformed) should use ``parse_openai_structured_response`` instead.

    Checks the SDK convenience ``output_text`` first, then the documented
    Responses API ``output`` message/content shape. Text content may be a
    direct string or the documented ``{"value": ...}`` text object.

    Reasoning, refusal, tool, and other non-text output items are ignored.
    Multiple text blocks are joined in response order so structured JSON is
    not silently truncated when the provider splits it across blocks.
    """
    if not isinstance(payload, dict):
        raise OpenAIResponseMalformed(reason="non_dict_payload")

    text_parts = _extract_openai_text_blocks(payload)
    if text_parts:
        return "".join(text_parts)
    raise OpenAIResponseMalformed(reason="no_text_output")


def _extract_openai_text_blocks(payload: dict) -> list[str]:
    """Return ordered assistant text blocks from a Responses payload without classification."""
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return [output_text]

    output = payload.get("output")
    if not isinstance(output, list):
        return []

    text_parts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") not in {None, "message"}:
            continue
        content_blocks = item.get("content")
        if not isinstance(content_blocks, list):
            continue
        for content in content_blocks:
            if not isinstance(content, dict) or content.get("type") not in {None, "output_text"}:
                continue
            text = content.get("text")
            if isinstance(text, dict):
                text = text.get("value")
            if isinstance(text, str) and text.strip():
                text_parts.append(text)
    return text_parts


def _response_contains_refusal(payload: dict) -> bool:
    """True when the payload contains a refusal output item or refusal content block."""
    output = payload.get("output")
    if not isinstance(output, list):
        return False
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "refusal":
            return True
        if item.get("type") in {None, "message"}:
            content_blocks = item.get("content")
            if not isinstance(content_blocks, list):
                continue
            for content in content_blocks:
                if isinstance(content, dict) and content.get("type") == "refusal":
                    return True
    return False


def _redacted_response_failure_reason(payload: dict) -> str:
    """Return only a code-like failure reason; provider messages stay discarded."""
    error = payload.get("error")
    if not isinstance(error, dict):
        return "unknown"
    return _redacted_provider_code(error.get("code") or error.get("type"))


def _attach_response_evidence(exc: Exception, payload: dict) -> Exception:
    """Attach only structured accounting/support evidence, never response bodies."""

    model = str(payload.get("model") or "") or None
    setattr(exc, "usage", dict(extract_openai_usage(payload, model=model) or {}))
    metadata = payload.get("_transport_metadata")
    setattr(exc, "transport_metadata", dict(metadata) if isinstance(metadata, dict) else {})
    setattr(exc, "provider_response_id", str(payload.get("id") or "") or None)
    provider_request_id = None
    if isinstance(metadata, dict):
        provider_request_id = str(metadata.get("provider_request_id") or "") or None
    setattr(exc, "provider_request_id", provider_request_id)
    return exc


def parse_openai_structured_response(payload: dict) -> str:
    """Classify a Responses API payload and return its JSON text.

    Success: returns the joined assistant text.
    Failure: raises a typed, redacted exception:

      - ``OpenAIResponseIncomplete``: status == "incomplete". Max-token
        truncation is retryable once locally; content filtering and unknown
        reasons are not retried with the identical prompt.
      - ``OpenAIResponseRefusal`` (non-retryable): the model refused the request.
      - ``OpenAIResponseFailed``: status == "failed" and is final. Retryable
        server failures are classified from their HTTP 5xx outcome instead.
      - ``OpenAIResponseMalformed`` (non-retryable): the response completed but
        carried no usable text.

    The typed classes let callers bound retries to incomplete or malformed
    output instead of re-validating partial JSON or blindly re-prompting
    refusals, which is the largest source of burned tokens and credits.
    """
    if not isinstance(payload, dict):
        raise OpenAIResponseMalformed(reason="response_payload_not_object")

    status = payload.get("status")
    if status == "incomplete":
        details = payload.get("incomplete_details")
        reason = details.get("reason") if isinstance(details, dict) else None
        exc = OpenAIResponseIncomplete(reason=reason, model=payload.get("model"), response_id=payload.get("id"))
        # Partial text is returned to the durable encrypted checkpoint owner;
        # it is never placed in metadata or logs.
        exc.partial_text = "".join(_extract_openai_text_blocks(payload))
        raise _attach_response_evidence(exc, payload)

    if status == "failed":
        raise _attach_response_evidence(OpenAIResponseFailed(
            reason=_redacted_response_failure_reason(payload),
            model=payload.get("model"),
            response_id=payload.get("id"),
        ), payload)

    if _response_contains_refusal(payload):
        raise _attach_response_evidence(
            OpenAIResponseRefusal(model=payload.get("model"), response_id=payload.get("id")),
            payload,
        )

    text_parts = _extract_openai_text_blocks(payload)
    if not text_parts:
        raise _attach_response_evidence(OpenAIResponseMalformed(
            reason="no_text_output",
            model=payload.get("model"),
            response_id=payload.get("id"),
        ), payload)
    return "".join(text_parts)


def extract_openai_usage(payload: dict, *, model: str | None = None) -> dict[str, int | float | str] | None:
    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return None

    input_tokens = _coerce_usage_int(
        usage.get("input_tokens"),
        usage.get("prompt_tokens"),
    )
    output_tokens = _coerce_usage_int(
        usage.get("output_tokens"),
        usage.get("completion_tokens"),
    )
    total_tokens = _coerce_usage_int(
        usage.get("total_tokens"),
        (input_tokens or 0) + (output_tokens or 0),
    )
    input_cached_tokens = _coerce_usage_int(
        ((usage.get("input_tokens_details") or {}) if isinstance(usage.get("input_tokens_details"), dict) else {}).get("cached_tokens")
    )

    if input_tokens is None and output_tokens is None and total_tokens is None and input_cached_tokens is None:
        return None

    normalized_model = (model or payload.get("model") or "").strip() or None
    estimated_cost_cents = _estimate_cost_cents(
        normalized_model,
        input_tokens=input_tokens or 0,
        output_tokens=output_tokens or 0,
    )
    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or ((input_tokens or 0) + (output_tokens or 0))),
        "input_cached_tokens": int(input_cached_tokens or 0),
        "estimated_cost_cents": estimated_cost_cents,
        "cost_source": "estimated" if estimated_cost_cents is not None else "unavailable",
        **({"model": normalized_model} if normalized_model else {}),
    }


def _coerce_usage_int(*values: object) -> int | None:
    for value in values:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _estimate_cost_cents(model: str | None, *, input_tokens: int, output_tokens: int) -> float | None:
    if not model:
        return None
    rates = _MODEL_COST_PER_1K_TOKENS_USD.get(model.strip().lower()) or _MODEL_COST_PER_1K_TOKENS_USD.get(model.strip())
    if rates is None:
        return None
    input_rate, output_rate = rates
    total_usd = (
        (Decimal(input_tokens) / Decimal(1000)) * input_rate
        + (Decimal(output_tokens) / Decimal(1000)) * output_rate
    )
    return float((total_usd * Decimal(100)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


@with_reliability(
    circuit_breaker=llm_circuit_breakers["openai"],
    retry_policy=_openai_retry_policy(),
    circuit_failure_predicate=_counts_as_openai_circuit_failure,
)
def call_openai_response(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    timeout: int | None = None,
    timeout_ceiling: int | None = None,
    max_output_tokens: int | None = None,
    response_format: dict | None = None,
    image_urls: list[str] | None = None,
    idempotency_key: str | None = None,
    client_request_id: str | None = None,
    recover_truncated_response: bool = False,
    public_web_research: bool = False,
) -> dict:
    """Call the OpenAI Responses API and return the parsed JSON response.

    Supports ``max_output_tokens`` and structured ``response_format``.
    HTTP and transport failures raise typed, redacted provider exceptions;
    only transient failures are retried or counted by the circuit breaker.
    
    Protected by circuit breaker and retry logic for production reliability.
    """
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for OpenAI generation.")

    user_content: list[dict[str, str]] = [{"type": "input_text", "text": user}]
    user_content.extend(
        {"type": "input_image", "image_url": image_url}
        for image_url in image_urls or []
        if image_url
    )
    request_payload: dict = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system}],
            },
            {
                "role": "user",
                "content": user_content,
            },
        ],
    }
    if public_web_research:
        # An explicit research caller owns a separate durable one-request budget.
        # No arbitrary tools or unbounded search loops enter generation requests.
        if model != "gpt-4.1-mini-2025-04-14" or not max_output_tokens or max_output_tokens > 2200:
            raise ValueError("Public research requires its bounded model/output policy")
        request_payload.update(tools=[{"type":"web_search", "search_context_size":"low"}],
            max_tool_calls=1, tool_choice="required", include=["web_search_call.action.sources"])
    if max_output_tokens is not None:
        request_payload["max_output_tokens"] = max(1, max_output_tokens)
    if response_format is not None:
        request_payload["text"] = {"format": response_format}

    logger.info(
        "OpenAI API call initiated",
        extra={
            "provider": "openai",
            "model": model,
            "max_output_tokens": max_output_tokens,
            "image_count": len(image_urls or []),
            "timeout": timeout,
        }
    )

    headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
    # Kept in the Python signature for caller compatibility only. OpenAI's
    # Responses POST documentation does not promise deduplication for a custom
    # Idempotency-Key, so it is deliberately not transmitted or replayed.
    _ = idempotency_key
    if client_request_id:
        headers["X-Client-Request-Id"] = client_request_id
    http_request = url_request.Request(
        url=OPENAI_RESPONSES_URL,
        data=json.dumps(request_payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    effective_timeout = _effective_timeout(timeout, timeout_ceiling=timeout_ceiling)
    read_deadline = time.monotonic() + effective_timeout
    try:
        with url_request.urlopen(http_request, timeout=effective_timeout) as response:
            metadata = {
                **_safe_response_metadata(response.headers, client_request_id=client_request_id),
                "http_status": int(response.status),
            }
            try:
                result = json.loads(response.read().decode("utf-8"))
            except IncompleteRead as exc:
                # A completed generation can be lost while reading its body.
                # Retrieve that same stored response once; never replay POST.
                match = re.match(rb'\s*\{\s*"id"\s*:\s*"(resp_[A-Za-z0-9_-]{1,200})"', exc.partial[:1024])
                remaining = read_deadline - time.monotonic()
                failure = OpenAITransportError(client_request_id=client_request_id)
                failure.retryable = False
                failure.transport_metadata = metadata
                if not recover_truncated_response or not match or remaining <= 0:
                    raise failure from None
                response_id = match[1].decode("ascii")
                failure.provider_response_id = response_id
                retrieve = url_request.Request(
                    url=f"{OPENAI_RESPONSES_URL}/{response_id}", headers=headers, method="GET",
                )
                metadata["response_retrieval_count"] = 1
                try:
                    with url_request.urlopen(retrieve, timeout=min(30.0, remaining)) as recovered:
                        result = json.loads(recovered.read().decode("utf-8"))
                        if not isinstance(result, dict) or result.get("id") != response_id or result.get("model") != model or time.monotonic() > read_deadline:
                            raise failure
                        metadata["response_retrieval_request_id"] = _safe_response_metadata(recovered.headers)["provider_request_id"]
                except (url_error.URLError, TimeoutError, OSError, IncompleteRead, ValueError):
                    raise failure from None
            result["_transport_metadata"] = metadata
            logger.info(
                "OpenAI API call successful",
                extra={
                    "provider": "openai",
                    "model": model,
                    "status_code": response.status,
                }
            )
            return result
    except url_error.HTTPError as exc:
        error_code = _openai_error_code(exc)
        metadata = _safe_response_metadata(exc.headers, client_request_id=client_request_id)
        retryable = (
            error_code not in _OPENAI_ACTION_REQUIRED_CODES
            and (error_code == "rate_limit_exceeded" or exc.code in {500, 502, 503, 504})
        )
        logger.error(
            "OpenAI API call failed with HTTP error",
            extra={
                "provider": "openai",
                "model": model,
                "status_code": exc.code,
                "error_code": error_code,
                "retryable": retryable,
            }
        )
        raise OpenAIHttpError(
            status_code=exc.code,
            code=error_code,
            retryable=retryable,
            provider_request_id=metadata["provider_request_id"],
            client_request_id=client_request_id,
            retry_after_seconds=metadata["retry_after_seconds"],
            rate_limit_metadata=metadata["rate_limit_metadata"],
        ) from exc
    except (url_error.URLError, TimeoutError, socket.timeout) as exc:
        logger.error(
            "OpenAI API call failed with network error",
            extra={
                "provider": "openai",
                "model": model,
                "error_type": type(exc).__name__,
            }
        )
        raise OpenAITransportError(client_request_id=client_request_id) from exc


def _effective_timeout(requested_timeout: int | None, *, timeout_ceiling: int | None = None) -> int:
    """Clamp *requested_timeout* to the configured maximum.

    General OpenAI calls are capped at ``openai_timeout_seconds`` (≤120s in
    production). Callers that legitimately need longer reads — the whole-deck
    ``full_html_deck.v1`` generation — may pass an explicit ``timeout_ceiling``
    bounded by ``instant_html_openai_timeout_seconds`` so the hard production
    safety cap on general calls is preserved.
    """
    if timeout_ceiling is not None:
        configured_timeout = max(
            1, min(max(1, timeout_ceiling), settings.instant_html_openai_timeout_seconds)
        )
    else:
        configured_timeout = max(1, settings.openai_timeout_seconds)
    if requested_timeout is None:
        return configured_timeout
    return max(1, min(requested_timeout, configured_timeout))


def check_openai_model_access(
    *, api_key: str, model: str, timeout: int = 10, force_refresh: bool = False
) -> dict[str, object]:
    """Verify model visibility with OpenAI's no-generation model retrieval API."""

    if not api_key or not model:
        return {"status": "not_configured", "verified": False, "model": model or None}
    cache_key = (_credential_hmac(api_key, key=_MODEL_ACCESS_CACHE_HMAC_KEY).hex(), model)
    now = time.monotonic()
    with _model_access_cache_lock:
        for stale_key, (cached_at, _value) in list(_model_access_cache.items()):
            if now - cached_at >= _MODEL_ACCESS_CACHE_TTL_SECONDS:
                _model_access_cache.pop(stale_key, None)
        cached = _model_access_cache.get(cache_key)
        if not force_refresh and cached:
            return dict(cached[1])
    request = url_request.Request(
        f"{OPENAI_MODELS_URL}/{model}",
        headers={"authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with url_request.urlopen(request, timeout=max(1, min(timeout, 15))) as response:
            payload = json.loads(response.read().decode("utf-8"))
            result = {
                "status": "verified" if response.status == 200 and payload.get("id") == model else "configured_unverified",
                "verified": response.status == 200 and payload.get("id") == model,
                "model": model,
                "providerRequestId": str(response.headers.get("x-request-id") or "")[:255] or None,
            }
    except url_error.HTTPError as exc:
        code = _openai_error_code(exc)
        result = {
            "status": "access_denied" if exc.code in {401, 403, 404} else "configured_unverified",
            "verified": False,
            "model": model,
            "httpStatus": exc.code,
            "errorCode": code,
            "providerRequestId": str(exc.headers.get("x-request-id") or "")[:255] or None,
        }
    except (url_error.URLError, TimeoutError, socket.timeout):
        result = {"status": "configured_unverified", "verified": False, "model": model}
    with _model_access_cache_lock:
        _model_access_cache[cache_key] = (time.monotonic(), result)
        while len(_model_access_cache) > _MODEL_ACCESS_CACHE_MAX_ENTRIES:
            oldest_key = min(_model_access_cache, key=lambda key: _model_access_cache[key][0])
            _model_access_cache.pop(oldest_key, None)
    return dict(result)


class OpenAIProvider(LLMProvider):
    """LLMProvider implementation backed by OpenAI's Responses API."""

    def __init__(self) -> None:
        self._provider_name = "openai"

    @property
    def name(self) -> str:
        return self._provider_name

    def generate_text(self, *, system: str | None = None, user: str, config: LlmGenerationConfig) -> LlmResponse:
        """Send a prompt to OpenAI and return the parsed response."""
        api_key = config.api_key
        if not api_key:
            raise ValueError("OpenAI API key is required")

        raw = call_openai_response(
            api_key=api_key,
            model=config.model,
            system=system or "",
            user=user,
            timeout=config.timeout_seconds,
            max_output_tokens=config.max_tokens,
            response_format=config.extra.get("response_format") if config.extra else None,
        )
        text = extract_openai_text(raw)
        return LlmResponse(
            content=text,
            model=config.model,
            provider=self._provider_name,
            usage=extract_openai_usage(raw, model=config.model),
            raw=raw,
        )

    def validate_connection(self, *, api_key: str, model: str | None = None) -> bool:
        """Verify the provider credentials by issuing a minimal API call."""
        try:
            call_openai_response(api_key=api_key, model=model or "gpt-4o", system="Say OK", user="OK", timeout=10)
            return True
        except Exception:
            return False
