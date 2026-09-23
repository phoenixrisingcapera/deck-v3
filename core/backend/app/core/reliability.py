"""Reliability utilities: circuit breakers, retry logic, and enhanced logging.

This module provides production-grade reliability patterns for external service calls.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open and rejecting calls."""
    pass


class CircuitBreaker:
    """Circuit breaker implementation for protecting against cascading failures.
    
    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Service is failing, calls are rejected immediately
    - HALF_OPEN: Testing if service has recovered
    
    The circuit opens after `failure_threshold` consecutive failures.
    It transitions to half-open after `recovery_timeout` seconds.
    A successful call in half-open state closes the circuit.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._half_open_generation = 0
        self._lock = threading.RLock()
        self._last_failure_time: float | None = None
        self._last_state_change: float = time.time()
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for automatic transitions."""
        with self._lock:
            return self._state_with_transition_locked()

    def _state_with_transition_locked(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has elapsed
            if self._last_failure_time and (time.time() - self._last_failure_time) >= self.recovery_timeout:
                self._transition_to_locked(CircuitState.HALF_OPEN)
        return self._state

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state with logging."""
        with self._lock:
            self._transition_to_locked(new_state)

    def _transition_to_locked(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._half_open_generation += 1
        
        logger.info(
            f"Circuit breaker '{self.name}' transitioned: {old_state.value} -> {new_state.value}",
            extra={
                "circuit_breaker": self.name,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "failure_count": self._failure_count,
            }
        )

    def _reserve_half_open_probe(self) -> tuple[CircuitState, int | None]:
        """Atomically observe state and reserve a probe slot for this cycle."""
        with self._lock:
            current_state = self._state_with_transition_locked()
            if current_state != CircuitState.HALF_OPEN:
                return current_state, None
            if self._half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerError(f"Circuit breaker '{self.name}' testing limit reached")
            self._half_open_calls += 1
            return current_state, self._half_open_generation
    
    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function through the circuit breaker."""
        current_state, _ = self._reserve_half_open_probe()
        
        if current_state == CircuitState.OPEN:
            logger.warning(
                f"Circuit breaker '{self.name}' is OPEN, rejecting call",
                extra={"circuit_breaker": self.name, "state": current_state.value}
            )
            raise CircuitBreakerError(f"Circuit breaker '{self.name}' is open")
        
        if current_state == CircuitState.HALF_OPEN:
            logger.debug(
                "Circuit breaker '%s' reserved a half-open probe",
                self.name,
                extra={"circuit_breaker": self.name, "calls": self._half_open_calls},
            )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def call_with_failure_predicate(
        self,
        func: Callable[..., T],
        *args,
        failure_predicate: Callable[[Exception], bool],
        **kwargs,
    ) -> T:
        """Execute while counting only exceptions selected as circuit failures."""
        current_state, half_open_generation = self._reserve_half_open_probe()
        if current_state == CircuitState.OPEN:
            raise CircuitBreakerError(f"Circuit breaker '{self.name}' is open")
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as exc:
            if failure_predicate(exc):
                self._on_failure()
            elif (
                half_open_generation is not None
                and self._state == CircuitState.HALF_OPEN
                and self._half_open_generation == half_open_generation
            ):
                # An ignored exception proves neither recovery nor circuit
                # failure, so release the probe slot for a future test call.
                with self._lock:
                    if (
                        self._state == CircuitState.HALF_OPEN
                        and self._half_open_generation == half_open_generation
                    ):
                        self._half_open_calls = max(0, self._half_open_calls - 1)
            raise
    
    def _on_success(self) -> None:
        """Handle successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                # Close circuit after successful half-open calls
                if self._success_count >= self.half_open_max_calls:
                    self._transition_to_locked(CircuitState.CLOSED)
                    self._failure_count = 0
                    self._success_count = 0
            else:
                # Reset failure count on success in closed state
                self._failure_count = 0
    
    def _on_failure(self) -> None:
        """Handle failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._transition_to_locked(CircuitState.OPEN)
                self._success_count = 0
            elif self._state == CircuitState.CLOSED:
                # Open circuit after threshold failures
                if self._failure_count >= self.failure_threshold:
                    self._transition_to_locked(CircuitState.OPEN)
    
    def get_status(self) -> dict[str, Any]:
        """Get circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": datetime.fromtimestamp(self._last_failure_time, tz=timezone.utc).isoformat() if self._last_failure_time else None,
            "last_state_change": datetime.fromtimestamp(self._last_state_change, tz=timezone.utc).isoformat(),
        }


class RetryPolicy:
    """Retry policy with exponential backoff and jitter.
    
    Implements retry logic with:
    - Exponential backoff: delay increases exponentially with each attempt
    - Jitter: random variation to prevent thundering herd
    - Maximum attempts: limit on retry attempts
    - Retryable exceptions: only retry on specific exception types
    """
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
        retry_predicate: Callable[[Exception], bool] | None = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions
        self.retry_predicate = retry_predicate

    def should_retry(self, exc: Exception) -> bool:
        """Return whether *exc* is eligible for another attempt."""
        return isinstance(exc, self.retryable_exceptions) and (
            self.retry_predicate is None or self.retry_predicate(exc)
        )
    
    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number."""
        # Exponential backoff
        delay = self.base_delay * (self.exponential_base ** attempt)
        
        # Cap at max delay
        delay = min(delay, self.max_delay)
        
        # Add jitter if enabled
        if self.jitter:
            import random
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_exception = e

                if self.retry_predicate is not None and not self.retry_predicate(e):
                    raise
                
                if attempt < self.max_attempts - 1:
                    delay = self.calculate_delay(attempt)
                    logger.warning(
                        f"Retry attempt {attempt + 1}/{self.max_attempts} after {delay:.2f}s",
                        extra={
                            "attempt": attempt + 1,
                            "max_attempts": self.max_attempts,
                            "delay": delay,
                            "exception": str(e),
                            "exception_type": type(e).__name__,
                        }
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {self.max_attempts} retry attempts failed",
                        extra={
                            "max_attempts": self.max_attempts,
                            "exception": str(e),
                            "exception_type": type(e).__name__,
                        }
                    )
        
        raise last_exception


def with_circuit_breaker(circuit_breaker: CircuitBreaker):
    """Decorator to wrap a function with circuit breaker protection."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return circuit_breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


def with_retry(retry_policy: RetryPolicy):
    """Decorator to wrap a function with retry logic."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            return retry_policy.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def with_reliability(
    circuit_breaker: CircuitBreaker | None = None,
    retry_policy: RetryPolicy | None = None,
    circuit_failure_predicate: Callable[[Exception], bool] | None = None,
):
    """Wrap a function with retry and transient-only circuit tracking.
    
    Order of execution:
    1. Circuit breaker check (fast fail if open)
    2. Retry logic (retry on failure)
    3. Circuit breaker result tracking (transient failures only)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            if circuit_breaker and retry_policy:
                # Retry inside the breaker while allowing the retry policy to
                # exclude permanent failures from transient circuit health.
                def execute_with_retry() -> T:
                    return retry_policy.execute(func, *args, **kwargs)

                return circuit_breaker.call_with_failure_predicate(
                    execute_with_retry,
                    failure_predicate=circuit_failure_predicate or retry_policy.should_retry,
                )
            elif circuit_breaker:
                return circuit_breaker.call(func, *args, **kwargs)
            elif retry_policy:
                return retry_policy.execute(func, *args, **kwargs)
            else:
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Pre-configured circuit breakers for LLM providers
llm_circuit_breakers = {
    "openai": CircuitBreaker("openai", failure_threshold=5, recovery_timeout=60),
    "anthropic": CircuitBreaker("anthropic", failure_threshold=5, recovery_timeout=60),
    "dashscope": CircuitBreaker("dashscope", failure_threshold=5, recovery_timeout=60),
    "openrouter": CircuitBreaker("openrouter", failure_threshold=5, recovery_timeout=60),
}

# Pre-configured retry policies for LLM providers
llm_retry_policies = {
    "openai": RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=30.0),
    "anthropic": RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=30.0),
    "dashscope": RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=30.0),
    "openrouter": RetryPolicy(max_attempts=3, base_delay=1.0, max_delay=30.0),
}


def get_circuit_breaker_status() -> dict[str, Any]:
    """Get status of all circuit breakers for monitoring."""
    return {
        name: cb.get_status()
        for name, cb in llm_circuit_breakers.items()
    }
