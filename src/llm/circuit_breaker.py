"""Circuit breaker implementation for rate-limited API providers.

Prevents cascading failures when external providers hit rate limits.
Uses three states: closed (normal), open (tripped), half-open (testing recovery).
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from typing import Callable, TypeVar, ParamSpec

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and request is rejected."""

    def __init__(self, message: str, cooldown_remaining: float):
        self.cooldown_remaining = cooldown_remaining
        super().__init__(message)


class RateLimitError(Exception):
    """Raised when provider returns HTTP 429 rate limit error."""

    pass


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""

    state: str  # closed, open, half_open
    failure_count: int
    success_count: int
    last_failure_time: float | None
    last_state_change: float
    open_count: int  # Total number of times circuit has opened
    half_open_attempts: int  # Number of half-open test requests


class CircuitBreaker:
    """Circuit breaker for handling rate-limited API providers.

    Implements the circuit breaker pattern:
    - Closed: Normal operation, all requests pass through
    - Open: After rate limit, fail-fast for cooldown period
    - Half-Open: After cooldown, allow 1 test request

    Example:
        >>> breaker = CircuitBreaker(cooldown_seconds=60)
        >>> try:
        ...     result = await breaker.call(api_request, "arg1", kwarg="value")
        ... except CircuitBreakerOpenError as e:
        ...     print(f"Circuit open, retry in {e.cooldown_remaining}s")
    """

    def __init__(self, cooldown_seconds: int = 60, name: str = "default"):
        """Initialize circuit breaker.

        Args:
            cooldown_seconds: Time to wait before attempting recovery (default: 60)
            name: Identifier for this circuit breaker (for logging)
        """
        self.cooldown_seconds = cooldown_seconds
        self.name = name
        self.state = "closed"  # closed, open, half_open
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self.last_state_change = time.time()
        self.open_count = 0
        self.half_open_attempts = 0

    async def call(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerOpenError: If circuit is open
            RateLimitError: If provider returns rate limit error
        """
        # Check if circuit should transition to half-open
        if self.state == "open":
            cooldown_elapsed = time.time() - (self.last_failure_time or 0)
            if cooldown_elapsed > self.cooldown_seconds:
                self._transition_to_half_open()
            else:
                cooldown_remaining = self.cooldown_seconds - cooldown_elapsed
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open. "
                    f"Retry in {cooldown_remaining:.1f}s",
                    cooldown_remaining=cooldown_remaining,
                )

        try:
            result = await func(*args, **kwargs)

            # Success in half-open state closes the circuit
            if self.state == "half_open":
                self._transition_to_closed()

            self.success_count += 1
            return result

        except RateLimitError as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == "half_open":
                # Test request failed, reopen circuit
                self._transition_to_open()
            elif self.state == "closed":
                # First failure, open circuit
                self._transition_to_open()

            raise

    def _transition_to_open(self) -> None:
        """Transition circuit to open state."""
        if self.state != "open":
            self.state = "open"
            self.open_count += 1
            self.last_state_change = time.time()
            logger.warning(
                f"Circuit breaker '{self.name}' OPENED "
                f"(failures: {self.failure_count}, cooldown: {self.cooldown_seconds}s)"
            )

    def _transition_to_half_open(self) -> None:
        """Transition circuit to half-open state."""
        self.state = "half_open"
        self.half_open_attempts += 1
        self.last_state_change = time.time()
        logger.info(
            f"Circuit breaker '{self.name}' entered HALF-OPEN state "
            f"(attempt: {self.half_open_attempts})"
        )

    def _transition_to_closed(self) -> None:
        """Transition circuit to closed state."""
        if self.state != "closed":
            self.state = "closed"
            self.last_state_change = time.time()
            logger.info(
                f"Circuit breaker '{self.name}' CLOSED "
                f"(successes: {self.success_count})"
            )

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get current circuit breaker metrics.

        Returns:
            CircuitBreakerMetrics with current state and counters
        """
        return CircuitBreakerMetrics(
            state=self.state,
            failure_count=self.failure_count,
            success_count=self.success_count,
            last_failure_time=self.last_failure_time,
            last_state_change=self.last_state_change,
            open_count=self.open_count,
            half_open_attempts=self.half_open_attempts,
        )

    def reset(self) -> None:
        """Reset circuit breaker to initial state (for testing)."""
        self.state = "closed"
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = time.time()
        logger.info(f"Circuit breaker '{self.name}' reset")
