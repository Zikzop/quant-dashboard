"""
Parametric VaR — distributional model-based risk quantification.

Parametric VaR assumes returns follow a known distribution and uses
its parameters (mean, variance, potentially df for Student-t) to
compute the quantile analytically.

Gaussian VaR: fast, simple, but UNDERESTIMATES tail risk.
Student-t VaR: captures fat tails via degrees-of-freedom parameter.
Cornish-Fisher: adjusts Gaussian quantile for skewness and kurtosis.

WARNING: Gaussian VaR systematically underestimates losses at the
99th percentile for financial returns, which universally exhibit
leptokurtosis (fat tails). The Student-t and Cornish-Fisher
corrections partially address this but remain parametric assumptions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from risk_engine.risk_config import VaRConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParametricVaRResult:
    """Parametric VaR results with multiple distributional models."""

    gaussian_var: dict[float, float]
    student_t_var: dict[float, float]
    cornish_fisher_var: dict[float, float]
    estimated_mean: float
    estimated_vol: float
    estimated_skewness: float
    estimated_kurtosis: float
    student_t_df: float
    n_observations: int


class ParametricVaREngine:
    """
    Computes parametric VaR under Gaussian, Student-t, and Cornish-Fisher models.

    The engine always computes all three for comparison, because:
    - The gap between Gaussian and Student-t reveals the fat-tail penalty
    - Cornish-Fisher adds skewness correction cheaply
    - Showing all three forces the user to confront model uncertainty
    """

    def __init__(self, config: VaRConfig | None = None) -> None:
        self._config = config or VaRConfig()

    def compute(
        self,
        returns: pd.Series,
        confidence_levels: tuple[float, ...] | None = None,
    ) -> ParametricVaRResult:
        levels = confidence_levels or self._config.confidence_levels
        r = returns.dropna().iloc[-self._config.lookback_days:]

        if len(r) < self._config.min_observations:
            empty = {cl: 0.0 for cl in levels}
            return ParametricVaRResult(
                gaussian_var=empty,
                student_t_var=empty,
                cornish_fisher_var=empty,
                estimated_mean=0.0,
                estimated_vol=0.0,
                estimated_skewness=0.0,
                estimated_kurtosis=0.0,
                student_t_df=30.0,
                n_observations=len(r),
            )

        mu = float(r.mean())
        sigma = float(r.std())
        skew = float(r.skew())
        kurt = float(r.kurtosis())

        try:
            df_fit, loc_fit, scale_fit = sp_stats.t.fit(r)
            df_fit = max(2.1, min(df_fit, 100.0))
        except Exception:
            df_fit = 5.0
            loc_fit = mu
            scale_fit = sigma

        gaussian_var = {}
        student_t_var = {}
        cf_var = {}

        for cl in levels:
            alpha = 1.0 - cl
            z = sp_stats.norm.ppf(alpha)
            gaussian_var[cl] = mu + sigma * z

            t_q = sp_stats.t.ppf(alpha, df=df_fit, loc=loc_fit, scale=scale_fit)
            student_t_var[cl] = float(t_q)

            z_cf = z + (z ** 2 - 1) * skew / 6.0 + (z ** 3 - 3 * z) * kurt / 24.0 - (2 * z ** 3 - 5 * z) * skew ** 2 / 36.0
            cf_var[cl] = mu + sigma * z_cf

        return ParametricVaRResult(
            gaussian_var=gaussian_var,
            student_t_var=student_t_var,
            cornish_fisher_var=cf_var,
            estimated_mean=mu,
            estimated_vol=sigma,
            estimated_skewness=skew,
            estimated_kurtosis=kurt,
            student_t_df=df_fit,
            n_observations=len(r),
        )
