"""
PnL engine — separates realized from unrealized, gross from net.

Proper PnL attribution requires tracking where returns come from:
- gross alpha PnL (before costs)
- slippage PnL drag
- spread PnL drag
- commission drag
- market impact drag

This separation is critical for understanding whether alpha exists
after real execution costs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PnLRecord:
    """Single-period PnL record."""

    timestamp: pd.Timestamp
    gross_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    slippage_cost: float
    spread_cost: float
    commission_cost: float
    impact_cost: float
    net_pnl: float
    portfolio_value: float
    cash: float


class PnLEngine:
    """Tracks period-by-period PnL decomposition."""

    def __init__(self) -> None:
        self._records: list[PnLRecord] = []
        self._prev_portfolio_value: float | None = None

    def record(
        self,
        timestamp: pd.Timestamp,
        portfolio_value: float,
        cash: float,
        realized_pnl: float,
        unrealized_pnl: float,
        slippage_cost: float = 0.0,
        spread_cost: float = 0.0,
        commission_cost: float = 0.0,
        impact_cost: float = 0.0,
    ) -> None:
        total_cost = slippage_cost + spread_cost + commission_cost + impact_cost
        gross_pnl = realized_pnl + unrealized_pnl
        net_pnl = gross_pnl - total_cost

        self._records.append(
            PnLRecord(
                timestamp=timestamp,
                gross_pnl=gross_pnl,
                realized_pnl=realized_pnl,
                unrealized_pnl=unrealized_pnl,
                slippage_cost=slippage_cost,
                spread_cost=spread_cost,
                commission_cost=commission_cost,
                impact_cost=impact_cost,
                net_pnl=net_pnl,
                portfolio_value=portfolio_value,
                cash=cash,
            )
        )
        self._prev_portfolio_value = portfolio_value

    def to_dataframe(self) -> pd.DataFrame:
        if not self._records:
            return pd.DataFrame()
        data = [
            {
                "timestamp": r.timestamp,
                "gross_pnl": r.gross_pnl,
                "realized_pnl": r.realized_pnl,
                "unrealized_pnl": r.unrealized_pnl,
                "slippage_cost": r.slippage_cost,
                "spread_cost": r.spread_cost,
                "commission_cost": r.commission_cost,
                "impact_cost": r.impact_cost,
                "net_pnl": r.net_pnl,
                "portfolio_value": r.portfolio_value,
                "cash": r.cash,
            }
            for r in self._records
        ]
        return pd.DataFrame(data).set_index("timestamp")

    def returns_series(self, gross: bool = False) -> pd.Series:
        df = self.to_dataframe()
        if df.empty:
            return pd.Series(dtype=float)
        col = "gross_pnl" if gross else "net_pnl"
        pv = df["portfolio_value"].shift(1)
        return (df[col] / pv.replace(0, np.nan)).dropna()

    def cost_drag(self) -> dict[str, float]:
        """Total cost drag as fraction of initial portfolio value."""
        df = self.to_dataframe()
        if df.empty:
            return {}
        initial = df["portfolio_value"].iloc[0]
        if initial <= 0:
            return {}
        return {
            "slippage_drag_pct": float(df["slippage_cost"].sum() / initial * 100),
            "spread_drag_pct": float(df["spread_cost"].sum() / initial * 100),
            "commission_drag_pct": float(df["commission_cost"].sum() / initial * 100),
            "impact_drag_pct": float(df["impact_cost"].sum() / initial * 100),
            "total_drag_pct": float(
                (df["slippage_cost"] + df["spread_cost"] + df["commission_cost"] + df["impact_cost"]).sum()
                / initial
                * 100
            ),
        }
