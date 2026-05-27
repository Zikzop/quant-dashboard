"""
Benchmark comparison — evaluate execution against market benchmarks.

Compares actual execution prices to:
- Market VWAP
- Market TWAP
- Arrival price
- Close price
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from execution_engine.execution_base import ExecutionResult, OrderSide

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BenchmarkReport:
    avg_fill_price: float
    arrival_price: float
    vwap_deviation_bps: float
    twap_deviation_bps: float
    arrival_deviation_bps: float
    close_deviation_bps: float
    best_benchmark: str
    worst_benchmark: str
    fill_ratio: float
    warnings: list[str] = field(default_factory=list)


class BenchmarkComparison:
    """Compare execution quality against standard benchmarks."""

    def compare(
        self,
        result: ExecutionResult,
        market_vwap: float | None = None,
        market_twap: float | None = None,
        closing_price: float | None = None,
    ) -> BenchmarkReport:
        warnings: list[str] = []

        fills = [f for c in result.child_orders for f in c.fill_events]
        if not fills:
            return BenchmarkReport(
                avg_fill_price=0.0, arrival_price=0.0,
                vwap_deviation_bps=0.0, twap_deviation_bps=0.0,
                arrival_deviation_bps=0.0, close_deviation_bps=0.0,
                best_benchmark="N/A", worst_benchmark="N/A",
                fill_ratio=0.0, warnings=["No fills"],
            )

        total_qty = sum(f.quantity_filled for f in fills)
        total_notional = sum(f.notional for f in fills)
        avg_fill = total_notional / total_qty if total_qty > 0 else 0.0

        arrival = fills[0].arrival_price if fills[0].arrival_price > 0 else avg_fill

        side_sign = 1.0 if result.parent_order.side == OrderSide.BUY else -1.0

        def deviation_bps(benchmark: float) -> float:
            if benchmark <= 0:
                return 0.0
            return side_sign * (avg_fill - benchmark) / benchmark * 10_000

        arrival_dev = deviation_bps(arrival)

        if market_vwap and market_vwap > 0:
            vwap_dev = deviation_bps(market_vwap)
        else:
            vwap_dev = 0.0
            warnings.append("No market VWAP available")

        if market_twap and market_twap > 0:
            twap_dev = deviation_bps(market_twap)
        else:
            twap_dev = 0.0

        if closing_price and closing_price > 0:
            close_dev = deviation_bps(closing_price)
        else:
            close_dev = 0.0

        deviations = {
            "arrival": abs(arrival_dev),
            "vwap": abs(vwap_dev),
            "twap": abs(twap_dev),
            "close": abs(close_dev),
        }
        non_zero = {k: v for k, v in deviations.items() if v > 0}
        best = min(non_zero, key=non_zero.get) if non_zero else "N/A"
        worst = max(non_zero, key=non_zero.get) if non_zero else "N/A"

        fill_ratio = (
            total_qty / result.parent_order.total_quantity
            if result.parent_order.total_quantity > 0
            else 0.0
        )

        return BenchmarkReport(
            avg_fill_price=avg_fill,
            arrival_price=arrival,
            vwap_deviation_bps=vwap_dev,
            twap_deviation_bps=twap_dev,
            arrival_deviation_bps=arrival_dev,
            close_deviation_bps=close_dev,
            best_benchmark=best,
            worst_benchmark=worst,
            fill_ratio=fill_ratio,
            warnings=warnings,
        )
