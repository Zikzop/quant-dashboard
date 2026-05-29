"""
Execution latency monitoring.

Tracks and analyzes latency across the execution pipeline:
- Order submission latency
- Fill acknowledgment latency
- End-to-end execution latency
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from execution_engine.execution_base import ExecutionResult, FillEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LatencyReport:
    mean_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    min_latency_ms: float
    std_latency_ms: float
    n_measurements: int
    outlier_count: int
    warnings: list[str] = field(default_factory=list)


class LatencyMonitor:
    """Track and analyze execution latency."""

    def __init__(self, outlier_threshold_ms: float = 500.0) -> None:
        self._threshold = outlier_threshold_ms

    def analyze(self, result: ExecutionResult) -> LatencyReport:
        warnings: list[str] = []

        fills = [f for c in result.child_orders for f in c.fill_events]
        if not fills:
            return LatencyReport(
                mean_latency_ms=0.0, median_latency_ms=0.0,
                p95_latency_ms=0.0, p99_latency_ms=0.0,
                max_latency_ms=0.0, min_latency_ms=0.0,
                std_latency_ms=0.0, n_measurements=0, outlier_count=0,
                warnings=["No fills to analyze"],
            )

        latencies = np.array([f.latency_ms for f in fills])
        outliers = int(np.sum(latencies > self._threshold))

        if outliers > 0:
            warnings.append(
                f"{outliers} fills exceeded {self._threshold:.0f}ms latency threshold"
            )

        return LatencyReport(
            mean_latency_ms=float(np.mean(latencies)),
            median_latency_ms=float(np.median(latencies)),
            p95_latency_ms=float(np.percentile(latencies, 95)),
            p99_latency_ms=float(np.percentile(latencies, 99)),
            max_latency_ms=float(np.max(latencies)),
            min_latency_ms=float(np.min(latencies)),
            std_latency_ms=float(np.std(latencies)),
            n_measurements=len(latencies),
            outlier_count=outliers,
            warnings=warnings,
        )
