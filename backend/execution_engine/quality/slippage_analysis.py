"""
Slippage analysis — post-trade analysis of execution slippage.

Decomposes total execution cost into slippage components and identifies
systematic patterns that indicate execution quality issues.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from execution_engine.execution_base import ExecutionResult, FillEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlippageReport:
    total_slippage_bps: float
    mean_slippage_bps: float
    median_slippage_bps: float
    std_slippage_bps: float
    max_slippage_bps: float
    p95_slippage_bps: float
    spread_component_bps: float
    impact_component_bps: float
    timing_component_bps: float
    n_fills: int
    adverse_fill_ratio: float
    warnings: list[str] = field(default_factory=list)


class SlippageAnalyzer:
    """Post-trade slippage decomposition and analysis."""

    def analyze(self, result: ExecutionResult) -> SlippageReport:
        warnings: list[str] = []
        fills = [f for c in result.child_orders for f in c.fill_events]

        if not fills:
            return SlippageReport(
                total_slippage_bps=0.0, mean_slippage_bps=0.0,
                median_slippage_bps=0.0, std_slippage_bps=0.0,
                max_slippage_bps=0.0, p95_slippage_bps=0.0,
                spread_component_bps=0.0, impact_component_bps=0.0,
                timing_component_bps=0.0, n_fills=0, adverse_fill_ratio=0.0,
                warnings=["No fills to analyze"],
            )

        slippages = [f.slippage_bps for f in fills]
        spreads = [f.spread_cost_bps for f in fills]
        impacts = [f.market_impact_bps for f in fills]
        notionals = [f.notional for f in fills]

        total_notional = sum(notionals)
        if total_notional > 0:
            weighted_slippage = sum(
                s * n for s, n in zip(slippages, notionals)
            ) / total_notional
            weighted_spread = sum(
                s * n for s, n in zip(spreads, notionals)
            ) / total_notional
            weighted_impact = sum(
                s * n for s, n in zip(impacts, notionals)
            ) / total_notional
        else:
            weighted_slippage = np.mean(slippages)
            weighted_spread = np.mean(spreads)
            weighted_impact = np.mean(impacts)

        timing = weighted_slippage - weighted_spread - weighted_impact

        arr = np.array(slippages)
        adverse = sum(1 for f in fills if f.implementation_shortfall_bps > 0)
        adverse_ratio = adverse / len(fills)

        if weighted_slippage > 20:
            warnings.append(
                f"High average slippage ({weighted_slippage:.1f} bps). "
                "Review execution algorithm and participation rates."
            )

        return SlippageReport(
            total_slippage_bps=weighted_slippage,
            mean_slippage_bps=float(np.mean(arr)),
            median_slippage_bps=float(np.median(arr)),
            std_slippage_bps=float(np.std(arr)),
            max_slippage_bps=float(np.max(arr)),
            p95_slippage_bps=float(np.percentile(arr, 95)),
            spread_component_bps=weighted_spread,
            impact_component_bps=weighted_impact,
            timing_component_bps=timing,
            n_fills=len(fills),
            adverse_fill_ratio=adverse_ratio,
            warnings=warnings,
        )
