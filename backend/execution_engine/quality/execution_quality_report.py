"""
Execution quality report — unified assessment of execution performance.

Aggregates slippage, implementation shortfall, latency, and benchmark
comparison into a single comprehensive report.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from execution_engine.execution_base import ExecutionResult
from execution_engine.quality.slippage_analysis import SlippageAnalyzer, SlippageReport
from execution_engine.quality.implementation_shortfall import (
    ImplementationShortfallAnalyzer,
    ISReport,
)
from execution_engine.quality.latency_monitor import LatencyMonitor, LatencyReport
from execution_engine.quality.benchmark_comparison import (
    BenchmarkComparison,
    BenchmarkReport,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionQualityReport:
    order_id: str
    symbol: str
    algorithm: str
    slippage: SlippageReport
    implementation_shortfall: ISReport
    latency: LatencyReport
    benchmark: BenchmarkReport
    overall_score: float
    grade: str
    warnings: list[str] = field(default_factory=list)


class ExecutionQualityAnalyzer:
    """
    Comprehensive execution quality assessment.

    Combines multiple quality metrics into a unified report with
    an overall score and letter grade.
    """

    def __init__(self) -> None:
        self._slippage = SlippageAnalyzer()
        self._is_analyzer = ImplementationShortfallAnalyzer()
        self._latency = LatencyMonitor()
        self._benchmark = BenchmarkComparison()

    def analyze(
        self,
        result: ExecutionResult,
        decision_price: float,
        closing_price: float | None = None,
        market_vwap: float | None = None,
        market_twap: float | None = None,
    ) -> ExecutionQualityReport:
        warnings: list[str] = []

        slip = self._slippage.analyze(result)
        warnings.extend(slip.warnings)

        is_report = self._is_analyzer.analyze(result, decision_price, closing_price)
        warnings.extend(is_report.warnings)

        lat = self._latency.analyze(result)
        warnings.extend(lat.warnings)

        bench = self._benchmark.compare(
            result, market_vwap=market_vwap, market_twap=market_twap,
        )
        warnings.extend(bench.warnings)

        score = self._compute_score(slip, is_report, lat, bench)
        grade = self._score_to_grade(score)

        algorithm = result.parent_order.algorithm.value if result.parent_order else "unknown"

        return ExecutionQualityReport(
            order_id=result.parent_order.order_id,
            symbol=result.parent_order.symbol,
            algorithm=algorithm,
            slippage=slip,
            implementation_shortfall=is_report,
            latency=lat,
            benchmark=bench,
            overall_score=score,
            grade=grade,
            warnings=warnings,
        )

    @staticmethod
    def _compute_score(
        slip: SlippageReport,
        is_report: ISReport,
        lat: LatencyReport,
        bench: BenchmarkReport,
    ) -> float:
        """
        Compute overall execution quality score [0, 100].

        Weights:
        - Slippage (30%): lower is better
        - Implementation shortfall (30%): lower is better
        - Latency (10%): lower is better
        - Benchmark tracking (30%): closer to benchmark is better
        """
        slip_score = max(0, 100 - slip.total_slippage_bps * 2)
        is_score = max(0, 100 - abs(is_report.total_is_bps) * 2)
        lat_score = max(0, 100 - lat.mean_latency_ms / 5)
        bench_score = max(0, 100 - abs(bench.vwap_deviation_bps) * 3)

        weighted = (
            0.30 * slip_score +
            0.30 * is_score +
            0.10 * lat_score +
            0.30 * bench_score
        )
        return float(max(0, min(100, weighted)))

    @staticmethod
    def _score_to_grade(score: float) -> str:
        if score >= 90:
            return "A"
        elif score >= 80:
            return "B"
        elif score >= 70:
            return "C"
        elif score >= 60:
            return "D"
        else:
            return "F"
