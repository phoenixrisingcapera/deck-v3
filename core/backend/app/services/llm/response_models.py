from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LlmResponse:
    content: str
    model: str | None = None
    provider: str | None = None
    usage: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None


def aggregate_usage(target: dict[str, Any] | None, usage: dict[str, Any] | None) -> None:
    """Accumulate safe provider accounting fields without retaining payloads."""
    if target is None or not isinstance(usage, dict):
        return
    for key in ("input_tokens", "output_tokens", "total_tokens", "input_cached_tokens"):
        target[key] = int(target.get(key) or 0) + max(0, int(usage.get(key) or 0))
    if usage.get("estimated_cost_cents") is not None:
        target["estimated_cost_cents"] = float(target.get("estimated_cost_cents") or 0.0) + max(
            0.0, float(usage["estimated_cost_cents"])
        )


@dataclass
class LlmGenerationConfig:
    model: str
    provider: str
    api_key: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    timeout_seconds: int | None = None
    extra: dict[str, Any] | None = None
