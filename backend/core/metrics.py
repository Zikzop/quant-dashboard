"""
Prometheus metrics for the research platform.

Tracked (per the hardening spec)
--------------------------------
* API latency                — ``api_request_latency_seconds``
* Cache hit ratio            — ``cache_events_total{level,result}``
* HMM failures               — ``model_fit_failures_total{model}``
* Fit durations              — ``model_fit_duration_seconds{model}``
* Signal frequency           — ``signal_emitted_total{signal}``
* Regime distribution drift  — ``regime_observed_total{regime,timeframe}``

The metrics module is import-safe (idempotent registration) so it can be
imported from tests and worker processes without ``Duplicated timeseries``
errors. Everything degrades to no-ops if ``prometheus_client`` is unavailable.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Histogram,
        generate_latest,
    )

    _HAS_PROM = True
except Exception:  # pragma: no cover
    _HAS_PROM = False
    CONTENT_TYPE_LATEST = "text/plain"


class _NoopMetric:
    def labels(self, *_a, **_k) -> "_NoopMetric":
        return self

    def inc(self, *_a, **_k) -> None:
        return None

    def observe(self, *_a, **_k) -> None:
        return None


def _counter(name: str, doc: str, labels: list[str]):
    if not _HAS_PROM:
        return _NoopMetric()
    try:
        return Counter(name, doc, labels)
    except ValueError:
        # Already registered (re-import in tests) — fetch the existing one.
        return REGISTRY._names_to_collectors[name]  # type: ignore[attr-defined]


def _histogram(name: str, doc: str, labels: list[str], buckets: tuple):
    if not _HAS_PROM:
        return _NoopMetric()
    try:
        return Histogram(name, doc, labels, buckets=buckets)
    except ValueError:
        return REGISTRY._names_to_collectors[name]  # type: ignore[attr-defined]


_LATENCY_BUCKETS = (0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0)
_FIT_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)

API_LATENCY = _histogram(
    "api_request_latency_seconds",
    "End-to-end API request latency.",
    ["endpoint", "asset", "timeframe", "status"],
    _LATENCY_BUCKETS,
)

CACHE_EVENTS = _counter(
    "cache_events_total",
    "Cache hit/miss events by cache level.",
    ["level", "result"],
)

FIT_DURATION = _histogram(
    "model_fit_duration_seconds",
    "Model fit duration (HMM/GARCH).",
    ["model", "timeframe"],
    _FIT_BUCKETS,
)

FIT_FAILURES = _counter(
    "model_fit_failures_total",
    "Model fit failures by model.",
    ["model"],
)

SIGNAL_EMITTED = _counter(
    "signal_emitted_total",
    "Signal frequency by signal label.",
    ["signal"],
)

REGIME_OBSERVED = _counter(
    "regime_observed_total",
    "Observed regime labels (for distribution drift).",
    ["regime", "timeframe"],
)

PROVIDER_ERRORS = _counter(
    "provider_errors_total",
    "Market data provider errors.",
    ["provider"],
)


def record_cache(level: str, hit: bool) -> None:
    CACHE_EVENTS.labels(level=level, result="hit" if hit else "miss").inc()


def record_signal(signal: str) -> None:
    SIGNAL_EMITTED.labels(signal=signal or "UNKNOWN").inc()


def record_regime(regime: str, timeframe: str) -> None:
    REGIME_OBSERVED.labels(regime=regime or "UNKNOWN", timeframe=timeframe).inc()


def record_fit_failure(model: str) -> None:
    FIT_FAILURES.labels(model=model).inc()


@contextmanager
def time_fit(model: str, timeframe: str) -> Iterator[None]:
    """Time a model fit and record its duration (and failures)."""
    start = time.perf_counter()
    try:
        yield
    except Exception:
        record_fit_failure(model)
        raise
    finally:
        FIT_DURATION.labels(model=model, timeframe=timeframe).observe(
            time.perf_counter() - start
        )


def render_latest() -> tuple[bytes, str]:
    """Return (payload, content_type) for the /metrics endpoint."""
    if not _HAS_PROM:
        return b"", CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST
