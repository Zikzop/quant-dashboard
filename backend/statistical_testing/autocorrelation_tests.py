"""
Autocorrelation and volatility clustering diagnostics.

Detects serial dependence in returns and squared returns (ARCH effects).
Uses backward-looking rolling windows only — no centered windows.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from statsmodels.stats.diagnostic import acorr_ljungbox

logger = logging.getLogger(__name__)

ClusteringLabel = Literal["none", "mild", "strong", "insufficient_data"]


@dataclass(frozen=True)
class LjungBoxResult:
    lags: tuple[int, ...]
    statistics: tuple[float, ...]
    p_values: tuple[float, ...]
    rejects_independence: bool
    interpretation: str


@dataclass(frozen=True)
class RollingAutocorrelation:
    lag: int
    series: pd.Series
    mean_acf: float
    interpretation: str


@dataclass(frozen=True)
class VolatilityClusteringDiagnostics:
    squared_returns_ljung_box: LjungBoxResult
    clustering: ClusteringLabel
    interpretation: str


@dataclass(frozen=True)
class AutocorrelationDiagnostics:
    returns_ljung_box: LjungBoxResult
    rolling_acf: RollingAutocorrelation | None
    volatility_clustering: VolatilityClusteringDiagnostics
    summary: str
    warnings: tuple[str, ...]


def run_ljung_box(
    series: pd.Series,
    *,
    lags: int | list[int] = 10,
    significance: float = 0.05,
) -> LjungBoxResult:
    """
    Ljung-Box test for serial correlation (null: no autocorrelation up to lag h).

    Significant p-values indicate autocorrelation — mean predictability or
    misspecified dynamics — not necessarily tradable alpha after costs.
    """
    clean = _clean_series(series)
    lag_list = [lags] if isinstance(lags, int) else list(lags)
    max_lag = max(lag_list)
    if len(clean) <= max_lag + 5:
        raise ValueError(f"Need more than {max_lag + 5} observations for Ljung-Box")

    result = acorr_ljungbox(clean.values, lags=lag_list, return_df=True)
    stats_arr = tuple(float(v) for v in result["lb_stat"].values)
    pvals = tuple(float(v) for v in result["lb_pvalue"].values)
    rejects = any(p < significance for p in pvals)

    if rejects:
        interp = (
            f"Reject no-autocorrelation null at {significance:.0%} "
            f"(min p={min(pvals):.4f}). Serial dependence detected."
        )
        logger.warning("Ljung-Box: serial correlation detected (min p=%.4f)", min(pvals))
    else:
        interp = (
            f"Fail to reject no-autocorrelation null (min p={min(pvals):.4f}). "
            "No strong evidence of linear serial dependence."
        )

    return LjungBoxResult(
        lags=tuple(lag_list),
        statistics=stats_arr,
        p_values=pvals,
        rejects_independence=rejects,
        interpretation=interp,
    )


def rolling_autocorrelation(
    series: pd.Series,
    *,
    lag: int = 1,
    window: int = 60,
    min_periods: int | None = None,
) -> RollingAutocorrelation:
    """
    Backward-looking rolling lag-1 autocorrelation.

    Window uses only past observations at each point (no center=True).
    """
    clean = _clean_series(series)
    min_p = min_periods or window

    def _lag_acf(x: np.ndarray) -> float:
        if len(x) < lag + 2:
            return np.nan
        s = pd.Series(x)
        return float(s.autocorr(lag=lag))

    rolling_acf = clean.rolling(window=window, min_periods=min_p).apply(_lag_acf, raw=True)
    mean_acf = float(rolling_acf.mean(skipna=True))

    if np.isnan(mean_acf):
        interp = "Insufficient data for rolling autocorrelation."
    elif abs(mean_acf) > 0.1:
        direction = "positive" if mean_acf > 0 else "negative"
        interp = f"Mean rolling ACF({lag})={mean_acf:.3f} suggests {direction} serial dependence."
    else:
        interp = f"Mean rolling ACF({lag})={mean_acf:.3f}; weak serial dependence."

    return RollingAutocorrelation(
        lag=lag,
        series=rolling_acf,
        mean_acf=mean_acf,
        interpretation=interp,
    )


def diagnose_volatility_clustering(
    returns: pd.Series,
    *,
    lags: int = 10,
    significance: float = 0.05,
) -> VolatilityClusteringDiagnostics:
    """
    Test autocorrelation in squared returns (ARCH / volatility clustering).

    Significant Ljung-Box on r² indicates time-varying volatility.
    """
    clean = _clean_series(returns)
    squared = clean**2

    if len(squared) < lags + 10:
        lb = LjungBoxResult(
            lags=(lags,),
            statistics=(float("nan"),),
            p_values=(float("nan"),),
            rejects_independence=False,
            interpretation="Insufficient data for volatility clustering test.",
        )
        return VolatilityClusteringDiagnostics(
            squared_returns_ljung_box=lb,
            clustering="insufficient_data",
            interpretation="Need more observations.",
        )

    lb = run_ljung_box(squared, lags=lags, significance=significance)
    min_p = min(lb.p_values)

    if lb.rejects_independence and min_p < 0.01:
        clustering: ClusteringLabel = "strong"
        interp = "Strong volatility clustering (ARCH effects). GARCH-class models warranted."
    elif lb.rejects_independence:
        clustering = "mild"
        interp = "Mild volatility clustering detected."
    else:
        clustering = "none"
        interp = "No significant autocorrelation in squared returns."

    return VolatilityClusteringDiagnostics(
        squared_returns_ljung_box=lb,
        clustering=clustering,
        interpretation=interp,
    )


def run_autocorrelation_diagnostics(
    returns: pd.Series,
    *,
    lags: int = 10,
    rolling_window: int = 60,
    significance: float = 0.05,
) -> AutocorrelationDiagnostics:
    """Full autocorrelation and volatility clustering diagnostic suite."""
    clean = _clean_series(returns)
    warnings: list[str] = []

    lb_returns = run_ljung_box(clean, lags=lags, significance=significance)
    rolling = (
        rolling_autocorrelation(clean, lag=1, window=rolling_window)
        if len(clean) >= rolling_window
        else None
    )
    vol_clust = diagnose_volatility_clustering(clean, lags=lags, significance=significance)

    if lb_returns.rejects_independence:
        warnings.append(
            "Return autocorrelation detected. Verify strategy does not exploit look-ahead."
        )

    summary = (
        f"Returns: {lb_returns.interpretation} "
        f"Vol clustering: {vol_clust.clustering}."
    )

    return AutocorrelationDiagnostics(
        returns_ljung_box=lb_returns,
        rolling_acf=rolling,
        volatility_clustering=vol_clust,
        summary=summary,
        warnings=tuple(warnings),
    )


def _clean_series(series: pd.Series) -> pd.Series:
    s = pd.Series(series).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        raise ValueError("Series is empty after removing NaN/inf")
    return s
