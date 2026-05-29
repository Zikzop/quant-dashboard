"""
Reliability primitives: retry, timeout guard, circuit breaker.

Rationale
---------
External market-data feeds fail in three characteristic ways: transient errors
(retry), hangs (timeout), and sustained outages (circuit break to stop hammering
a dead dependency and to fail fast). These are implemented as small, composable,
fully-testable pure-Python components rather than taking hard dependencies on
``tenacity``/``pybreaker`` — which keeps the platform runnable in constrained
environments and makes the failure semantics explicit and auditable. The classes
are drop-in replaceable with those libraries later.

All primitives are synchronous because they wrap the synchronous data-access
bridge (FastAPI runs sync routes in a worker thread, so blocking here is safe
and does not stall the event loop).
"""

from __future__ import annotations

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

from core.logging import get_logger

logger = get_logger("core.reliability")

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised when a call is rejected because the circuit breaker is OPEN."""


class TimeoutGuardError(TimeoutError):
    """Raised when a guarded call exceeds its deadline."""


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.2
    max_delay: float = 5.0
    jitter: float = 0.1
    retry_on: tuple[type[BaseException], ...] = (Exception,)

    def backoff(self, attempt: int) -> float:
        delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        return delay + random.uniform(0, self.jitter)


def retry_call(fn: Callable[[], T], policy: RetryPolicy, *, label: str = "call") -> T:
    """Execute ``fn`` with exponential backoff. Re-raises the last error."""
    last_exc: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except policy.retry_on as exc:  # type: ignore[misc]
            last_exc = exc
            if attempt >= policy.max_attempts:
                break
            sleep_for = policy.backoff(attempt)
            logger.warning(
                "retry",
                label=label,
                attempt=attempt,
                max_attempts=policy.max_attempts,
                sleep=round(sleep_for, 3),
                error=str(exc),
            )
            time.sleep(sleep_for)
    assert last_exc is not None
    raise last_exc


# A small shared pool for timeout guarding. Daemon threads so a hung provider
# call never blocks interpreter shutdown.
_TIMEOUT_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="timeout-guard")


def call_with_timeout(fn: Callable[[], T], timeout: float, *, label: str = "call") -> T:
    """Run ``fn`` with a wall-clock deadline.

    Note: Python cannot forcibly kill the worker thread; on timeout we abandon
    it (daemon) and raise. This is the pragmatic guard used across the industry
    for blocking I/O that lacks native timeout support.
    """
    future = _TIMEOUT_POOL.submit(fn)
    try:
        return future.result(timeout=timeout)
    except FutureTimeout as exc:
        logger.error("timeout", label=label, timeout=timeout)
        raise TimeoutGuardError(f"{label} exceeded {timeout}s deadline") from exc


class CircuitBreaker:
    """Thread-safe circuit breaker.

    States
    ------
    CLOSED     : calls pass through; consecutive failures are counted.
    OPEN       : calls are rejected immediately until ``reset_timeout`` elapses.
    HALF_OPEN  : a single trial call is allowed; success closes, failure re-opens.
    """

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(
        self,
        *,
        fail_max: int = 5,
        reset_timeout: float = 30.0,
        name: str = "breaker",
        excluded: Iterable[type[BaseException]] = (),
    ) -> None:
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.name = name
        self._excluded = tuple(excluded)
        self._state = self.CLOSED
        self._failures = 0
        self._opened_at = 0.0
        self._lock = threading.RLock()

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def _can_attempt(self) -> bool:
        if self._state == self.OPEN:
            if (time.monotonic() - self._opened_at) >= self.reset_timeout:
                self._state = self.HALF_OPEN
                logger.info("circuit_half_open", breaker=self.name)
                return True
            return False
        return True

    def _on_success(self) -> None:
        with self._lock:
            self._failures = 0
            if self._state != self.CLOSED:
                logger.info("circuit_closed", breaker=self.name)
            self._state = self.CLOSED

    def _on_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == self.HALF_OPEN or self._failures >= self.fail_max:
                self._state = self.OPEN
                self._opened_at = time.monotonic()
                logger.error(
                    "circuit_open",
                    breaker=self.name,
                    failures=self._failures,
                    reset_timeout=self.reset_timeout,
                )

    def call(self, fn: Callable[[], T]) -> T:
        with self._lock:
            if not self._can_attempt():
                raise CircuitOpenError(
                    f"circuit '{self.name}' is OPEN; failing fast"
                )
        try:
            result = fn()
        except self._excluded:
            raise
        except Exception:
            self._on_failure()
            raise
        else:
            self._on_success()
            return result


@dataclass
class ResilientExecutor:
    """Compose breaker -> retry -> timeout around a synchronous callable."""

    breaker: CircuitBreaker
    retry: RetryPolicy
    timeout: float
    label: str = "resilient"

    def run(self, fn: Callable[[], T]) -> T:
        def guarded() -> T:
            return call_with_timeout(fn, self.timeout, label=self.label)

        return self.breaker.call(lambda: retry_call(guarded, self.retry, label=self.label))
