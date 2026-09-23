"""Canonical Qwen routing policy for DeckAiStack.

This module provides the single source of truth for which Qwen model handles
each operation type (generation, critique, repair, embedding, vision).

It does NOT replace the existing provider resolver — it extends it with
explicit model routing for the Qwen strategy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QwenRoutingDecision:
    provider: str
    strategy: str
    model: str
    operation: str
    timeout_seconds: int
    max_tokens: int
    temperature: float
    max_retries: int
    fallback_provider: str | None
    fallback_model: str | None


@dataclass
class QwenTokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    model: str | None = None
    provider: str | None = None
    operation: str | None = None
    job_id: str | None = None
    workspace_id: str | None = None
    latency_ms: float = 0.0
    retry_count: int = 0
    error_category: str | None = None
    recorded_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "provider": self.provider,
            "operation": self.operation,
            "job_id": self.job_id,
            "workspace_id": self.workspace_id,
            "latency_ms": self.latency_ms,
            "retry_count": self.retry_count,
            "error_category": self.error_category,
            "recorded_at": (self.recorded_at or datetime.now(timezone.utc)).isoformat(),
        }


def extract_token_usage(raw_response: dict, **kwargs) -> QwenTokenUsage:
    usage = raw_response.get("usage") or {}
    if isinstance(usage, dict):
        input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (input_tokens + output_tokens))
    else:
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0

    return QwenTokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model=kwargs.get("model"),
        provider=kwargs.get("provider"),
        operation=kwargs.get("operation"),
        job_id=kwargs.get("job_id"),
        workspace_id=kwargs.get("workspace_id"),
        latency_ms=kwargs.get("latency_ms", 0.0),
        retry_count=kwargs.get("retry_count", 0),
        error_category=kwargs.get("error_category"),
        recorded_at=datetime.now(timezone.utc),
    )


def resolve_qwen_routing(operation: str, preferred_model: str | None = None) -> QwenRoutingDecision:
    strategy = settings.effective_qwen_strategy
    provider = "dashscope"

    if operation == "generation":
        model = preferred_model or settings.effective_qwen_model
    elif operation == "critique":
        model = settings.effective_qwen_critique_model
    elif operation == "repair":
        model = settings.effective_qwen_repair_model
    elif operation == "embedding":
        model = settings.qwen_embedding_model or "text-embedding-v3"
    elif operation == "vision":
        model = settings.qwen_vision_model or settings.effective_qwen_model
    else:
        model = preferred_model or settings.effective_qwen_model

    return QwenRoutingDecision(
        provider=provider,
        strategy=strategy,
        model=model,
        operation=operation,
        timeout_seconds=settings.effective_qwen_timeout,
        max_tokens=settings.qwen_max_output_tokens,
        temperature=settings.qwen_temperature,
        max_retries=settings.qwen_max_retries,
        fallback_provider=settings.qwen_fallback_provider or None,
        fallback_model=settings.qwen_fallback_model or None,
    )


def is_retryable_error(error: Exception) -> bool:
    message = str(error).lower()
    non_retryable = [
        "authentication",
        "unauthorized",
        "401",
        "403",
        "invalid_api_key",
        "quota_exceeded",
        "rate_limit",
        "429",
        "insufficient_quota",
    ]
    return not any(code in message for code in non_retryable)


def check_quota_limit(usage: QwenTokenUsage) -> tuple[bool, str | None]:
    if usage.total_tokens > settings.qwen_max_tokens_per_job:
        return False, f"Job token limit exceeded: {usage.total_tokens} > {settings.qwen_max_tokens_per_job}"
    return True, None


def get_qwen_health_summary() -> dict[str, Any]:
    from app.services.llm.embedding_service import get_embedding_metrics

    configured = bool(settings.effective_qwen_api_key)
    base_url = settings.dashscope_base_url or ""
    region = "international" if "intl" in base_url else "china" if base_url else None

    return {
        "configured": configured,
        "provider": "dashscope",
        "strategy": settings.effective_qwen_strategy,
        "generation_model": settings.effective_qwen_model if configured else None,
        "critique_model": settings.effective_qwen_critique_model if configured else None,
        "repair_model": settings.effective_qwen_repair_model if configured else None,
        "embedding_model": settings.qwen_embedding_model if configured else None,
        "embedding_dimensions": settings.embedding_dimensions if configured else None,
        "embedding_fallback_models": [
            model.strip()
            for model in settings.embedding_fallback_models.split(",")
            if model.strip()
        ],
        "embedding_metrics": get_embedding_metrics(),
        "vision_model": settings.qwen_vision_model if configured and settings.qwen_vision_model else None,
        "base_url_region": region,
        "workspace_configured": bool(settings.dashscope_workspace_id),
        "fallback_enabled": settings.qwen_fallback_enabled,
        "fallback_provider": settings.qwen_fallback_provider or None,
        "fallback_model": settings.qwen_fallback_model or None,
        "max_tokens_per_job": settings.qwen_max_tokens_per_job,
        "max_repair_attempts": settings.qwen_max_repair_attempts,
        "temperature": settings.qwen_temperature,
        "timeout_seconds": settings.effective_qwen_timeout,
    }
