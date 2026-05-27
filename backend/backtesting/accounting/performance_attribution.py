"""
Performance attribution — decomposes returns by source.

Attribution answers: where did the returns come from?
- Which alphas contributed? (alpha attribution)
- Which instruments? (instrument attribution)
- Long vs short book? (direction attribution)
- Gross alpha vs cost drag? (cost attribution)

Without attribution, you cannot improve a strategy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AttributionResult:
    """Performance attribution decomposition."""

    total_return: float
    gross_alpha_return: float
    cost_drag: float
    long_contribution: float
    short_contribution: float
    alpha_contributions: dict[str, float]
    instrument_contributions: dict[str, float]
    cost_breakdown: dict[str, float]


class PerformanceAttribution:
    """
    Decomposes portfolio returns by source.

    Requires trade-level data and daily portfolio snapshots.
    """

    def __init__(self) -> None:
        self._daily_records: list[dict] = []
        self._alpha_pnl: dict[str, float] = {}
        self._instrument_pnl: dict[str, float] = {}

    def record_daily(
        self,
        timestamp: pd.Timestamp,
        portfolio_value: float,
        long_pnl: float,
        short_pnl: float,
        total_costs: float,
        alpha_pnl: dict[str, float] | None = None,
        instrument_pnl: dict[str, float] | None = None,
    ) -> None:
        self._daily_records.append({
            "timestamp": timestamp,
            "portfolio_value": portfolio_value,
            "long_pnl": long_pnl,
            "short_pnl": short_pnl,
            "total_costs": total_costs,
        })

        if alpha_pnl:
            for name, pnl in alpha_pnl.items():
                self._alpha_pnl[name] = self._alpha_pnl.get(name, 0.0) + pnl
        if instrument_pnl:
            for sym, pnl in instrument_pnl.items():
                self._instrument_pnl[sym] = self._instrument_pnl.get(sym, 0.0) + pnl

    def compute(self, cost_breakdown: dict[str, float] | None = None) -> AttributionResult:
        if not self._daily_records:
            return AttributionResult(
                total_return=0.0,
                gross_alpha_return=0.0,
                cost_drag=0.0,
                long_contribution=0.0,
                short_contribution=0.0,
                alpha_contributions={},
                instrument_contributions={},
                cost_breakdown={},
            )

        df = pd.DataFrame(self._daily_records)
        initial_pv = df["portfolio_value"].iloc[0]
        final_pv = df["portfolio_value"].iloc[-1]
        total_return = (final_pv / initial_pv) - 1 if initial_pv > 0 else 0.0

        total_costs = df["total_costs"].sum()
        long_total = df["long_pnl"].sum()
        short_total = df["short_pnl"].sum()
        gross = long_total + short_total

        return AttributionResult(
            total_return=total_return,
            gross_alpha_return=gross / max(initial_pv, 1e-9),
            cost_drag=total_costs / max(initial_pv, 1e-9),
            long_contribution=long_total / max(initial_pv, 1e-9),
            short_contribution=short_total / max(initial_pv, 1e-9),
            alpha_contributions={
                k: v / max(initial_pv, 1e-9)
                for k, v in self._alpha_pnl.items()
            },
            instrument_contributions={
                k: v / max(initial_pv, 1e-9)
                for k, v in self._instrument_pnl.items()
            },
            cost_breakdown=cost_breakdown or {},
        )
