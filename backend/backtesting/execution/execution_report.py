"""
Execution report — aggregated execution quality diagnostics.

Tracks slippage, spread costs, market impact, and fill quality
across the entire backtest for post-mortem analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtesting.event_engine.events import FillEvent, FillStatus

logger = logging.getLogger(__name__)


@dataclass
class ExecutionReport:
    """Accumulates fill events and produces execution quality metrics."""

    _fills: list[FillEvent] = field(default_factory=list)

    def record(self, fill: FillEvent) -> None:
        self._fills.append(fill)

    def to_dataframe(self) -> pd.DataFrame:
        if not self._fills:
            return pd.DataFrame()
        records = []
        for f in self._fills:
            records.append({
                "timestamp": f.timestamp,
                "symbol": f.symbol,
                "side": f.side.value,
                "quantity_ordered": f.quantity_ordered,
                "quantity_filled": f.quantity_filled,
                "fill_price": f.fill_price,
                "slippage": f.slippage,
                "spread_cost": f.spread_cost,
                "market_impact": f.market_impact,
                "commission": f.commission,
                "total_cost": f.total_cost,
                "fill_status": f.fill_status.value,
                "latency_ms": f.latency_ms,
                "fill_ratio": f.quantity_filled / max(f.quantity_ordered, 1e-9),
            })
        return pd.DataFrame(records)

    def summary(self) -> dict[str, float]:
        if not self._fills:
            return {}
        df = self.to_dataframe()
        filled = df[df["fill_status"] == FillStatus.FILLED.value]
        return {
            "total_fills": len(self._fills),
            "filled_count": len(filled),
            "partial_count": len(df[df["fill_status"] == FillStatus.PARTIAL.value]),
            "rejected_count": len(df[df["fill_status"] == FillStatus.REJECTED.value]),
            "fill_rate": len(filled) / max(len(self._fills), 1),
            "total_slippage": float(df["slippage"].sum()),
            "total_spread_cost": float(df["spread_cost"].sum()),
            "total_market_impact": float(df["market_impact"].sum()),
            "total_commission": float(df["commission"].sum()),
            "total_execution_cost": float(df["total_cost"].sum()),
            "mean_slippage_per_fill": float(df["slippage"].mean()),
            "mean_latency_ms": float(df["latency_ms"].mean()),
            "median_fill_ratio": float(df["fill_ratio"].median()),
            "p95_slippage": float(np.percentile(df["slippage"].dropna(), 95))
            if len(df) > 0
            else 0.0,
        }
