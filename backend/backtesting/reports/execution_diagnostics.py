"""
Execution diagnostics — measures execution quality and cost efficiency.

Answers questions like:
- How much did slippage cost us?
- Are we getting filled at reasonable prices?
- Is market impact material?
- How does execution degrade as we scale?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.execution.execution_report import ExecutionReport

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionDiagnostics:
    """Execution quality diagnostics."""

    total_fills: int
    fill_rate: float
    mean_slippage_bps: float
    median_slippage_bps: float
    p95_slippage_bps: float
    total_slippage_cost: float
    total_spread_cost: float
    total_impact_cost: float
    total_commission: float
    total_execution_cost: float
    cost_as_pct_of_pv: float
    mean_latency_ms: float
    partial_fill_rate: float
    avg_fill_ratio: float


def compute_execution_diagnostics(
    exec_report: ExecutionReport,
    portfolio_value: float,
) -> ExecutionDiagnostics:
    """Compute execution quality metrics from fill records."""
    summary = exec_report.summary()
    if not summary:
        return ExecutionDiagnostics(
            total_fills=0, fill_rate=0, mean_slippage_bps=0,
            median_slippage_bps=0, p95_slippage_bps=0,
            total_slippage_cost=0, total_spread_cost=0,
            total_impact_cost=0, total_commission=0,
            total_execution_cost=0, cost_as_pct_of_pv=0,
            mean_latency_ms=0, partial_fill_rate=0, avg_fill_ratio=0,
        )

    df = exec_report.to_dataframe()
    filled = df[df["fill_status"] != "REJECTED"]

    if len(filled) > 0 and (filled["fill_price"] > 0).any():
        valid = filled[filled["fill_price"] > 0]
        slip_bps = (valid["slippage"] / (valid["fill_price"] * valid["quantity_filled"].abs())) * 10000
        mean_slip = float(slip_bps.mean())
        med_slip = float(slip_bps.median())
        p95_slip = float(np.percentile(slip_bps.dropna(), 95)) if len(slip_bps.dropna()) > 0 else 0
    else:
        mean_slip = med_slip = p95_slip = 0

    total_exec_cost = summary.get("total_execution_cost", 0)

    return ExecutionDiagnostics(
        total_fills=int(summary.get("total_fills", 0)),
        fill_rate=float(summary.get("fill_rate", 0)),
        mean_slippage_bps=mean_slip,
        median_slippage_bps=med_slip,
        p95_slippage_bps=p95_slip,
        total_slippage_cost=float(summary.get("total_slippage", 0)),
        total_spread_cost=float(summary.get("total_spread_cost", 0)),
        total_impact_cost=float(summary.get("total_market_impact", 0)),
        total_commission=float(summary.get("total_commission", 0)),
        total_execution_cost=total_exec_cost,
        cost_as_pct_of_pv=total_exec_cost / max(portfolio_value, 1e-9) * 100,
        mean_latency_ms=float(summary.get("mean_latency_ms", 0)),
        partial_fill_rate=float(summary.get("partial_count", 0)) / max(summary.get("total_fills", 1), 1),
        avg_fill_ratio=float(summary.get("median_fill_ratio", 0)),
    )
