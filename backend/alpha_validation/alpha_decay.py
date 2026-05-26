"""
Alpha decay analysis: rolling performance deterioration detection.

Identifies regime-dependent alpha erosion via backward-looking rolling metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

TRADING_DAYS = 252.0
DecayLabel = Literal["stable", "mild_decay", "severe_decay", "insufficient_data"]


@dataclass(frozen=True)
class AlphaDecayConfig:
    rolling_window: int = 63
    min_periods: int | None = None
    risk_free_rate: float = 0.02
    decay_threshold: float = -0.5


@dataclass(frozen=True)
class RollingMetricSeries:
    metric_name: str
    series: pd.Series
    current_value: float
    trend_slope: float
    interpretation: str


@dataclass(frozen=True)
class AlphaDecayAnalysis:
    rolling_sharpe: RollingMetricSeries
    rolling_expectancy: RollingMetricSeries
    rolling_hit_rate: RollingMetricSeries
    decay_assessment: DecayLabel
    summary: str
    warnings: tuple[str, ...]


def analyze_alpha_decay(
    returns: pd.Series,
    *,
    config: AlphaDecayConfig | None = None,
) -> AlphaDecayAnalysis:
    """
    Analyze rolling Sharpe, expectancy, and hit rate for alpha deterioration.

    Uses backward-looking windows only. Trend slope estimated via OLS on
    rolling metric time series (diagnostic, not predictive).
    """
    cfg = config or AlphaDecayConfig()
    clean = _clean_returns(returns)
    min_p = cfg.min_periods or cfg.rolling_window
    warnings: list[str] = []

    if len(clean) < cfg.rolling_window + 10:
        empty = pd.Series(dtype=float)
        placeholder = RollingMetricSeries(
            metric_name="n/a",
            series=empty,
            current_value=float("nan"),
            trend_slope=float("nan"),
            interpretation="Insufficient data.",
        )
        return AlphaDecayAnalysis(
            rolling_sharpe=placeholder,
            rolling_expectancy=placeholder,
            rolling_hit_rate=placeholder,
            decay_assessment="insufficient_data",
            summary="Insufficient observations for alpha decay analysis.",
            warnings=("Need more data than rolling_window + 10.",),
        )

    sharpe_series = _rolling_sharpe(clean, cfg.rolling_window, min_p, cfg.risk_free_rate)
    expectancy_series = clean.rolling(cfg.rolling_window, min_periods=min_p).mean()
    hit_rate_series = (clean > 0).astype(float).rolling(cfg.rolling_window, min_periods=min_p).mean()

    sharpe = _build_metric("rolling_sharpe", sharpe_series)
    expectancy = _build_metric("rolling_expectancy", expectancy_series)
    hit_rate = _build_metric("rolling_hit_rate", hit_rate_series)

    decay_signals = 0
    if sharpe.trend_slope < cfg.decay_threshold:
        decay_signals += 1
        warnings.append(f"Sharpe trend slope={sharpe.trend_slope:.3f} indicates deterioration.")
    if expectancy.trend_slope < 0:
        decay_signals += 1
    if hit_rate.trend_slope < -0.001:
        decay_signals += 1

    if decay_signals >= 2:
        assessment: DecayLabel = "severe_decay"
        summary = "Multiple metrics show alpha deterioration; investigate regime shift."
        logger.warning("Alpha decay: severe deterioration detected")
    elif decay_signals == 1:
        assessment = "mild_decay"
        summary = "Mild alpha decay in one metric; monitor OOS performance."
    else:
        assessment = "stable"
        summary = "Rolling metrics stable; no strong decay signal."

    warnings.append(
        "Rolling trends are descriptive. Structural breaks may not appear as smooth decay."
    )

    return AlphaDecayAnalysis(
        rolling_sharpe=sharpe,
        rolling_expectancy=expectancy,
        rolling_hit_rate=hit_rate,
        decay_assessment=assessment,
        summary=summary,
        warnings=tuple(warnings),
    )


def _rolling_sharpe(
    returns: pd.Series,
    window: int,
    min_periods: int,
    risk_free_rate: float,
) -> pd.Series:
    rf_daily = risk_free_rate / TRADING_DAYS

    def _sharpe_window(x: np.ndarray) -> float:
        if len(x) < 2 or np.std(x, ddof=1) == 0:
            return np.nan
        excess = x - rf_daily
        return float(excess.mean() / np.std(x, ddof=1) * np.sqrt(TRADING_DAYS))

    return returns.rolling(window, min_periods=min_periods).apply(_sharpe_window, raw=True)


def _build_metric(name: str, series: pd.Series) -> RollingMetricSeries:
    valid = series.dropna()
    if valid.empty:
        return RollingMetricSeries(
            metric_name=name,
            series=series,
            current_value=float("nan"),
            trend_slope=float("nan"),
            interpretation="No valid rolling observations.",
        )

    current = float(valid.iloc[-1])
    x = np.arange(len(valid))
    slope, _, _, p_value, _ = stats.linregress(x, valid.values)

    if slope < -0.01 and p_value < 0.05:
        interp = f"{name} declining (slope={slope:.4f}, p={p_value:.4f})."
    elif slope > 0.01 and p_value < 0.05:
        interp = f"{name} improving (slope={slope:.4f}, p={p_value:.4f})."
    else:
        interp = f"{name} trend flat or insignificant (slope={slope:.4f})."

    return RollingMetricSeries(
        metric_name=name,
        series=series,
        current_value=current,
        trend_slope=float(slope),
        interpretation=interp,
    )


def _clean_returns(returns: pd.Series) -> pd.Series:
    s = pd.Series(returns).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        raise ValueError("Return series is empty")
    return s.sort_index()
