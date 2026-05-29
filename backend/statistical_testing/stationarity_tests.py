"""
Stationarity diagnostics for financial time series.

Tests whether a series exhibits time-invariant statistical properties.
Non-stationarity implies spurious inference if ignored in modeling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import adfuller, kpss

logger = logging.getLogger(__name__)

StationarityLabel = Literal["stationary", "non_stationary", "inconclusive", "insufficient_data"]


@dataclass(frozen=True)
class ADFResult:
    statistic: float
    p_value: float
    used_lag: int
    n_obs: int
    critical_values: dict[str, float]
    interpretation: str
    rejects_unit_root: bool


@dataclass(frozen=True)
class KPSSResult:
    statistic: float
    p_value: float
    n_lags: int
    critical_values: dict[str, float]
    interpretation: str
    rejects_stationarity: bool


@dataclass(frozen=True)
class HurstResult:
    exponent: float
    interpretation: str
    regime_hint: Literal["mean_reverting", "random_walk", "trending", "insufficient_data"]


@dataclass(frozen=True)
class StationarityAssessment:
    adf: ADFResult | None
    kpss: KPSSResult | None
    hurst: HurstResult
    assessment: StationarityLabel
    summary: str
    warnings: tuple[str, ...]


def run_adf(
    series: pd.Series,
    *,
    maxlag: int | None = None,
    regression: str = "c",
    significance: float = 0.05,
) -> ADFResult:
    """
    Augmented Dickey-Fuller test for unit root (null: non-stationary).

    A low p-value rejects the unit root null, supporting stationarity.
    """
    clean = _clean_series(series)
    if len(clean) < 10:
        raise ValueError("ADF requires at least 10 observations")

    result = adfuller(clean.values, maxlag=maxlag, regression=regression, autolag="AIC")
    stat, p_value, used_lag, nobs, crit, _ = result
    rejects = p_value < significance

    if rejects:
        interp = (
            f"Reject unit root at {significance:.0%} level (p={p_value:.4f}). "
            "Evidence supports stationarity."
        )
    else:
        interp = (
            f"Fail to reject unit root (p={p_value:.4f}). "
            "Series may be non-stationary or have insufficient power."
        )
        logger.warning("ADF: weak evidence against unit root (p=%.4f)", p_value)

    return ADFResult(
        statistic=float(stat),
        p_value=float(p_value),
        used_lag=int(used_lag),
        n_obs=int(nobs),
        critical_values={k: float(v) for k, v in crit.items()},
        interpretation=interp,
        rejects_unit_root=rejects,
    )


def run_kpss(
    series: pd.Series,
    *,
    regression: str = "c",
    nlags: str = "auto",
    significance: float = 0.05,
) -> KPSSResult:
    """
    KPSS test (null: stationarity around deterministic trend/mean).

    Complements ADF: rejection here indicates non-stationarity.
    """
    clean = _clean_series(series)
    if len(clean) < 10:
        raise ValueError("KPSS requires at least 10 observations")

    stat, p_value, lags, crit = kpss(clean.values, regression=regression, nlags=nlags)
    rejects = p_value < significance

    if rejects:
        interp = (
            f"Reject stationarity null at {significance:.0%} (p={p_value:.4f}). "
            "Series exhibits non-stationary behavior."
        )
        logger.warning("KPSS: rejects stationarity (p=%.4f)", p_value)
    else:
        interp = (
            f"Fail to reject stationarity null (p={p_value:.4f}). "
            "Consistent with stationary process."
        )

    return KPSSResult(
        statistic=float(stat),
        p_value=float(p_value),
        n_lags=int(lags),
        critical_values={k: float(v) for k, v in crit.items()},
        interpretation=interp,
        rejects_stationarity=rejects,
    )


def estimate_hurst_exponent(series: pd.Series, *, max_lag: int | None = None) -> HurstResult:
    """
    Rescaled-range (R/S) Hurst exponent estimate.

    H < 0.5: mean-reverting tendency
    H ≈ 0.5: random-walk-like
    H > 0.5: persistent / trending tendency

    Note: Hurst is a long-memory heuristic, not a formal stationarity test.
    """
    clean = _clean_series(series).values
    n = len(clean)
    if n < 20:
        return HurstResult(
            exponent=float("nan"),
            interpretation="Insufficient data for Hurst estimation (n < 20).",
            regime_hint="insufficient_data",
        )

    max_lag = max_lag or min(n // 2, 100)
    lags = range(2, max(3, max_lag))
    rs_vals: list[float] = []
    lag_vals: list[float] = []

    for lag in lags:
        segments = n // lag
        if segments < 1:
            continue
        rs_segment: list[float] = []
        for seg in range(segments):
            chunk = clean[seg * lag : (seg + 1) * lag]
            mean_adj = chunk - chunk.mean()
            cumdev = np.cumsum(mean_adj)
            r = cumdev.max() - cumdev.min()
            s = chunk.std(ddof=1)
            if s > 0:
                rs_segment.append(r / s)
        if rs_segment:
            rs_vals.append(np.log(np.mean(rs_segment)))
            lag_vals.append(np.log(lag))

    if len(lag_vals) < 2:
        return HurstResult(
            exponent=float("nan"),
            interpretation="Could not compute R/S regression for Hurst exponent.",
            regime_hint="insufficient_data",
        )

    slope, _, _, _, _ = stats.linregress(lag_vals, rs_vals)
    h = float(slope)

    if h < 0.45:
        hint: Literal["mean_reverting", "random_walk", "trending", "insufficient_data"] = "mean_reverting"
        interp = f"H={h:.3f} suggests anti-persistent (mean-reverting) dynamics."
    elif h > 0.55:
        hint = "trending"
        interp = f"H={h:.3f} suggests persistent (trend-following) dynamics."
    else:
        hint = "random_walk"
        interp = f"H={h:.3f} consistent with random-walk-like behavior."

    return HurstResult(exponent=h, interpretation=interp, regime_hint=hint)


def run_stationarity_suite(
    series: pd.Series,
    *,
    significance: float = 0.05,
) -> StationarityAssessment:
    """
    Run ADF, KPSS, and Hurst diagnostics with combined assessment.

    ADF and KPSS have opposing nulls; conflicting results yield ``inconclusive``.
    """
    warnings: list[str] = []
    clean = _clean_series(series)

    if len(clean) < 20:
        return StationarityAssessment(
            adf=None,
            kpss=None,
            hurst=HurstResult(
                exponent=float("nan"),
                interpretation="Insufficient data.",
                regime_hint="insufficient_data",
            ),
            assessment="insufficient_data",
            summary="Fewer than 20 observations; stationarity tests unreliable.",
            warnings=("Increase sample size before drawing inference.",),
        )

    adf = run_adf(clean, significance=significance)
    kpss = run_kpss(clean, significance=significance)
    hurst = estimate_hurst_exponent(clean)

    if adf.rejects_unit_root and not kpss.rejects_stationarity:
        assessment: StationarityLabel = "stationary"
        summary = "ADF and KPSS agree: evidence supports stationarity."
    elif not adf.rejects_unit_root and kpss.rejects_stationarity:
        assessment = "non_stationary"
        summary = "ADF and KPSS agree: evidence supports non-stationarity."
    else:
        assessment = "inconclusive"
        summary = (
            "ADF/KPSS conflict or weak significance. "
            "Consider differencing, detrending, or structural break tests."
        )
        warnings.append("Conflicting or weak stationarity evidence.")

    if adf.p_value > 0.10 and not adf.rejects_unit_root:
        warnings.append(f"ADF p-value={adf.p_value:.4f} indicates weak power against unit root.")

    return StationarityAssessment(
        adf=adf,
        kpss=kpss,
        hurst=hurst,
        assessment=assessment,
        summary=summary,
        warnings=tuple(warnings),
    )


def _clean_series(series: pd.Series) -> pd.Series:
    s = pd.Series(series).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if s.empty:
        raise ValueError("Series is empty after removing NaN/inf")
    return s
