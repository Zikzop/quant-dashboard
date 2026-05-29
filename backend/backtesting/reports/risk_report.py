"""
Risk report — exposure, drawdown, tail risk, and constraint analysis.

A backtest is incomplete without risk analysis. This report covers:
- Exposure evolution over time
- Drawdown analysis
- Tail risk metrics (VaR, CVaR)
- Leverage utilization
- Concentration risk
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskReport:
    """Comprehensive risk analysis of a backtest."""

    max_gross_leverage: float
    avg_gross_leverage: float
    max_net_exposure: float
    max_position_concentration: float
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    max_drawdown: float
    max_drawdown_duration_days: int
    avg_drawdown: float
    n_drawdowns_gt_5pct: int
    longest_underwater_days: int
    skewness: float
    kurtosis: float
    downside_deviation: float
    constraint_violations: int
    warnings: tuple[str, ...]


def compute_risk_report(
    returns: pd.Series,
    leverage_series: pd.Series | None = None,
    exposure_series: pd.Series | None = None,
    constraint_violation_count: int = 0,
) -> RiskReport:
    """Compute comprehensive risk metrics from a return series."""
    r = returns.dropna().values
    warnings: list[str] = []

    var_95 = float(np.percentile(r, 5))
    var_99 = float(np.percentile(r, 1))
    tail_5 = r[r <= var_95]
    tail_1 = r[r <= var_99]
    cvar_95 = float(np.mean(tail_5)) if len(tail_5) > 0 else var_95
    cvar_99 = float(np.mean(tail_1)) if len(tail_1) > 0 else var_99

    equity = np.cumprod(1 + r)
    running_max = np.maximum.accumulate(equity)
    dd = (equity - running_max) / np.maximum(running_max, 1e-9)
    max_dd = float(np.min(dd))

    underwater = dd < -0.001
    if np.any(underwater):
        changes = np.diff(underwater.astype(int))
        starts = np.where(changes == 1)[0]
        ends = np.where(changes == -1)[0]
        if len(starts) > 0:
            if len(ends) == 0 or ends[-1] < starts[-1]:
                ends = np.append(ends, len(dd) - 1)
            durations = []
            for s, e in zip(starts, ends):
                durations.append(e - s)
            longest_uw = max(durations) if durations else 0
        else:
            longest_uw = 0
    else:
        longest_uw = 0

    dd_depths = []
    in_dd = False
    current_depth = 0.0
    dd_start = 0
    max_dd_duration = 0
    dd_count_gt5 = 0

    for i, d in enumerate(dd):
        if d < -0.001 and not in_dd:
            in_dd = True
            dd_start = i
            current_depth = d
        elif in_dd and d < current_depth:
            current_depth = d
        elif in_dd and d >= 0:
            dd_depths.append(current_depth)
            duration = i - dd_start
            max_dd_duration = max(max_dd_duration, duration)
            if current_depth < -0.05:
                dd_count_gt5 += 1
            in_dd = False

    if in_dd:
        dd_depths.append(current_depth)
        max_dd_duration = max(max_dd_duration, len(dd) - dd_start)
        if current_depth < -0.05:
            dd_count_gt5 += 1

    max_lev = avg_lev = 0.0
    if leverage_series is not None and len(leverage_series) > 0:
        max_lev = float(leverage_series.max())
        avg_lev = float(leverage_series.mean())

    max_net = 0.0
    max_conc = 0.0
    if exposure_series is not None and len(exposure_series) > 0:
        max_net = float(exposure_series.abs().max())

    downside = r[r < 0]
    downside_dev = float(np.std(downside, ddof=1) * np.sqrt(252)) if len(downside) > 1 else 0.0

    skew = float(pd.Series(r).skew())
    kurt = float(pd.Series(r).kurtosis())

    if max_dd < -0.20:
        warnings.append(f"Max drawdown {max_dd:.1%} exceeds 20% — severe")
    if kurt > 5:
        warnings.append(f"Excess kurtosis {kurt:.1f} — heavy tails present")
    if skew < -0.5:
        warnings.append(f"Negative skewness {skew:.2f} — asymmetric downside risk")
    if constraint_violation_count > 0:
        warnings.append(f"{constraint_violation_count} constraint violations during backtest")

    return RiskReport(
        max_gross_leverage=max_lev,
        avg_gross_leverage=avg_lev,
        max_net_exposure=max_net,
        max_position_concentration=max_conc,
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        max_drawdown=max_dd,
        max_drawdown_duration_days=max_dd_duration,
        avg_drawdown=float(np.mean(dd_depths)) if dd_depths else 0.0,
        n_drawdowns_gt_5pct=dd_count_gt5,
        longest_underwater_days=longest_uw,
        skewness=skew,
        kurtosis=kurt,
        downside_deviation=downside_dev,
        constraint_violations=constraint_violation_count,
        warnings=tuple(warnings),
    )
