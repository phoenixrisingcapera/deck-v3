from __future__ import annotations

import time
from dataclasses import dataclass


class OperationDeadlineExceeded(TimeoutError):
    """Raised when the whole logical LLM operation has no time remaining."""


@dataclass(frozen=True)
class OperationDeadline:
    expires_at: float

    @classmethod
    def after(cls, seconds: float, *, clock=time.monotonic) -> "OperationDeadline":
        if seconds <= 0:
            raise ValueError("Operation deadline must be positive.")
        return cls(expires_at=clock() + seconds)

    def remaining(self, *, clock=time.monotonic) -> float:
        return max(0.0, self.expires_at - clock())

    def require_remaining(self, minimum_seconds: float = 0.0, *, clock=time.monotonic) -> float:
        remaining = self.remaining(clock=clock)
        if remaining <= minimum_seconds:
            raise OperationDeadlineExceeded("The AI operation exceeded its deadline.")
        return remaining

    def provider_timeout(self, configured_timeout: float, *, reserve_seconds: float = 1.0, clock=time.monotonic) -> float:
        remaining = self.require_remaining(reserve_seconds, clock=clock) - reserve_seconds
        return max(0.1, min(configured_timeout, remaining))
