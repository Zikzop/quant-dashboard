"""
Turnover engine — tracks and constrains portfolio turnover.

High turnover destroys alpha through transaction costs.
This engine measures two-sided turnover as a fraction of portfolio value
and can gate excessive trading.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TurnoverEngine:
    """
    Tracks realized turnover per period and cumulative.

    turnover = sum(|trade_notional|) / portfolio_value
    """

    _daily_turnover: dict[pd.Timestamp, float] = field(default_factory=lambda: defaultdict(float))
    _cumulative_traded: float = 0.0

    def record_trade(
        self,
        timestamp: pd.Timestamp,
        notional: float,
    ) -> None:
        self._daily_turnover[timestamp] += abs(notional)
        self._cumulative_traded += abs(notional)

    def daily_turnover(self, timestamp: pd.Timestamp, portfolio_value: float) -> float:
        if portfolio_value <= 0:
            return 0.0
        return self._daily_turnover.get(timestamp, 0.0) / portfolio_value

    def cumulative_turnover(self, portfolio_value: float) -> float:
        if portfolio_value <= 0:
            return 0.0
        return self._cumulative_traded / portfolio_value

    def annualized_turnover(
        self, portfolio_value: float, trading_days: int
    ) -> float:
        if trading_days <= 0 or portfolio_value <= 0:
            return 0.0
        daily_avg = self._cumulative_traded / trading_days
        return (daily_avg / portfolio_value) * 252

    def can_trade(
        self,
        timestamp: pd.Timestamp,
        proposed_notional: float,
        portfolio_value: float,
        max_daily_turnover: float,
    ) -> bool:
        current = self.daily_turnover(timestamp, portfolio_value)
        proposed_fraction = abs(proposed_notional) / max(portfolio_value, 1e-9)
        return (current + proposed_fraction) <= max_daily_turnover

    def to_series(self, portfolio_values: dict[pd.Timestamp, float]) -> pd.Series:
        """Daily turnover time series."""
        data = {}
        for ts, traded in sorted(self._daily_turnover.items()):
            pv = portfolio_values.get(ts, 1.0)
            data[ts] = traded / max(pv, 1e-9)
        return pd.Series(data, name="daily_turnover")
