"""Reliability primitive tests: retry, timeout guard, circuit breaker."""

from __future__ import annotations

import time

import pytest

from core.reliability import (
    CircuitBreaker,
    CircuitOpenError,
    ResilientExecutor,
    RetryPolicy,
    TimeoutGuardError,
    call_with_timeout,
    retry_call,
)


def test_retry_succeeds_after_transient_failures():
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] < 3:
            raise ValueError("transient")
        return "ok"

    assert retry_call(flaky, RetryPolicy(max_attempts=5, base_delay=0.0, jitter=0.0)) == "ok"
    assert state["n"] == 3


def test_retry_exhausts_and_reraises():
    def always_fail():
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError, match="permanent"):
        retry_call(always_fail, RetryPolicy(max_attempts=2, base_delay=0.0, jitter=0.0))


def test_timeout_guard_raises():
    with pytest.raises(TimeoutGuardError):
        call_with_timeout(lambda: time.sleep(0.3) or 1, timeout=0.05)


def test_timeout_guard_passes_fast_calls():
    assert call_with_timeout(lambda: 7, timeout=1.0) == 7


def test_circuit_breaker_opens_and_recovers():
    cb = CircuitBreaker(fail_max=2, reset_timeout=0.05, name="t")

    def fail():
        raise RuntimeError("x")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb.call(fail)
    assert cb.state == CircuitBreaker.OPEN

    with pytest.raises(CircuitOpenError):
        cb.call(lambda: 1)

    time.sleep(0.06)
    assert cb.call(lambda: "recovered") == "recovered"
    assert cb.state == CircuitBreaker.CLOSED


def test_resilient_executor_composition():
    cb = CircuitBreaker(fail_max=5, reset_timeout=1.0, name="exec")
    ex = ResilientExecutor(
        breaker=cb,
        retry=RetryPolicy(max_attempts=3, base_delay=0.0, jitter=0.0),
        timeout=1.0,
    )
    state = {"n": 0}

    def flaky():
        state["n"] += 1
        if state["n"] < 2:
            raise ValueError("retry me")
        return 99

    assert ex.run(flaky) == 99
