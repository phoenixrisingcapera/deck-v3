from __future__ import annotations

from typing import Any


PROVIDER_CAPACITY_MARKERS = (
    "AllocationQuota.FreeTierOnly",
    "insufficient_quota",
    "quota_exceeded",
    "DashScope request failed with status 429",
    "DashScope request failed with status 503",
    "DashScope request failed with status 504",
)


def is_non_retryable_provider_error(exc: Exception) -> bool:
    from app.services.llm.openai_provider import (
        OpenAIHttpError,
        OpenAIResponseFailed,
        OpenAIResponseIncomplete,
        OpenAIResponseMalformed,
        OpenAIResponseRefusal,
    )

    if isinstance(
        exc,
        (
            OpenAIResponseRefusal,
            OpenAIResponseFailed,
            OpenAIResponseMalformed,
            OpenAIResponseIncomplete,
        ),
    ):
        # These errors reach the durable boundary only after any bounded local
        # structured-output retry has completed. Requeueing the same expensive
        # prompt would repeat terminal output or restart an exhausted retry.
        return True
    return isinstance(exc, OpenAIHttpError) and not exc.retryable


def is_provider_capacity_error(exc: Exception) -> bool:
    from app.core.reliability import CircuitBreakerError
    from app.services.llm.openai_provider import OpenAIHttpError

    if isinstance(exc, CircuitBreakerError):
        return True
    if isinstance(exc, OpenAIHttpError):
        return exc.retryable and exc.code in {"rate_limit_exceeded", "provider_server_error"}
    message = str(exc)
    return any(marker.lower() in message.lower() for marker in PROVIDER_CAPACITY_MARKERS if marker != "insufficient_quota")


def provider_capacity_error_detail(*, feature: str) -> dict[str, Any]:
    return {
        "code": "provider_temporarily_unavailable",
        "message": f"{feature} is temporarily unavailable because AI provider capacity is exhausted. Retry after capacity recovers or connect another provider.",
        "recoverable": True,
        "nextAction": "configure_provider_or_retry",
    }
