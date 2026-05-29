"""
Equity curve — portfolio value over time with drawdown analysis.

The equity curve is the most important output of any backtest.
It shows not just the terminal return but the path — which matters
because drawdowns determine whether a strategy survives in practice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DrawdownPeriod:
    """A single drawdown episode."""

    start: pd.Timestamp
    trough: pd.Timestamp
    end: pd.Timestamp | None
    depth: float
    duration_days: int
    recovery_days: int | None


@dataclass(frozen=True)
class EquityCurveAnalysis:
    """Comprehensive equity curve analysis."""

    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_duration_days: int
    calmar_ratio: float
    avg_drawdown: float
    n_drawdowns: int
    longest_drawdown_days: int
    underwater_pct: float
    skewness: float
    kurtosis: float
    worst_month: float
    best_month: float


class EquityCurveBuilder:
    """Builds and analyzes equity curves from portfolio value snapshots."""

    def __init__(self) -> None:
        self._values: list[tuple[pd.Timestamp, float]] = []

    def record(self, timestamp: pd.Timestamp, portfolio_value: float) -> None:
        self._values.append((timestamp, portfolio_value))

    def to_series(self) -> pd.Series:
        if not self._values:
            return pd.Series(dtype=float)
        ts, vals = zip(*self._values)
        return pd.Series(vals, index=pd.DatetimeIndex(ts), name="portfolio_value")

    def returns(self) -> pd.Series:
        eq = self.to_series()
        return eq.pct_change().dropna()

    def drawdown_series(self) -> pd.Series:
        eq = self.to_series()
        if eq.empty:
            return pd.Series(dtype=float)
        running_max = eq.cummax()
        return (eq - running_max) / running_max

    def find_drawdowns(self, threshold: float = -0.01) -> list[DrawdownPeriod]:
        """Identify distinct drawdown periods exceeding the threshold."""
        dd = self.drawdown_series()
        if dd.empty:
            return []

        drawdowns: list[DrawdownPeriod] = []
        in_drawdown = False
        start = None
        trough_idx = None
        trough_val = 0.0

        for i, (ts, val) in enumerate(dd.items()):
            if val < threshold and not in_drawdown:
                in_drawdown = True
                start = ts
                trough_idx = ts
                trough_val = val
            elif in_drawdown and val < trough_val:
                trough_idx = ts
                trough_val = val
            elif in_drawdown and val >= 0:
                drawdowns.append(
                    DrawdownPeriod(
                        start=start,
                        trough=trough_idx,
                        end=ts,
                        depth=trough_val,
                        duration_days=(ts - start).days,
                        recovery_days=(ts - trough_idx).days,
                    )
                )
                in_drawdown = False

        if in_drawdown:
            drawdowns.append(
                DrawdownPeriod(
                    start=start,
                    trough=trough_idx,
                    end=None,
                    depth=trough_val,
                    duration_days=(dd.index[-1] - start).days,
                    recovery_days=None,
                )
            )

        return drawdowns

    def analyze(self, risk_free_rate: float = 0.02) -> EquityCurveAnalysis:
        """Comprehensive equity curve analysis."""
        eq = self.to_series()
        if len(eq) < 2:
            raise ValueError("Need at least 2 data points for analysis")

        r = eq.pct_change().dropna()
        n_days = len(r)
        years = n_days / 252

        total_ret = (eq.iloc[-1] / eq.iloc[0]) - 1
        ann_ret = (1 + total_ret) ** (1 / max(years, 1e-9)) - 1
        ann_vol = float(r.std() * np.sqrt(252))
        rf_daily = risk_free_rate / 252
        excess = r - rf_daily
        sharpe = float(excess.mean() / max(r.std(), 1e-9) * np.sqrt(252))

        downside = r[r < 0]
        downside_std = float(downside.std()) if len(downside) > 0 else 1e-9
        sortino = float(excess.mean() / max(downside_std, 1e-9) * np.sqrt(252))

        dd = self.drawdown_series()
        max_dd = float(dd.min())
        calmar = ann_ret / max(abs(max_dd), 1e-9)

        drawdowns = self.find_drawdowns()
        dd_depths = [d.depth for d in drawdowns]
        dd_durations = [d.duration_days for d in drawdowns]
        underwater = float((dd < -0.001).mean())

        monthly = r.resample("ME").apply(lambda x: (1 + x).prod() - 1)

        return EquityCurveAnalysis(
            total_return=float(total_ret),
            annualized_return=float(ann_ret),
            annualized_volatility=ann_vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            max_drawdown_duration_days=max(dd_durations) if dd_durations else 0,
            calmar_ratio=float(calmar),
            avg_drawdown=float(np.mean(dd_depths)) if dd_depths else 0.0,
            n_drawdowns=len(drawdowns),
            longest_drawdown_days=max(dd_durations) if dd_durations else 0,
            underwater_pct=underwater,
            skewness=float(r.skew()),
            kurtosis=float(r.kurtosis()),
            worst_month=float(monthly.min()) if len(monthly) > 0 else 0.0,
            best_month=float(monthly.max()) if len(monthly) > 0 else 0.0,
        )
