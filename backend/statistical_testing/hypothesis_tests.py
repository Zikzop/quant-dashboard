"""
Hypothesis testing utilities for alpha validation workflows.

Supports parametric and bootstrap inference with explicit assumptions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Literal

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

Alternative = Literal["two-sided", "greater", "less"]


@dataclass(frozen=True)
class TTestResult:
    statistic: float
    p_value: float
    mean: float
    std: float
    n_obs: int
    alternative: Alternative
    rejects_null: bool
    interpretation: str
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class ConfidenceIntervalResult:
    point_estimate: float
    lower: float
    upper: float
    confidence_level: float
    method: str
    interpretation: str


@dataclass(frozen=True)
class BootstrapSignificanceResult:
    observed_statistic: float
    bootstrap_mean: float
    bootstrap_std: float
    p_value: float
    confidence_interval: ConfidenceIntervalResult
    n_bootstrap: int
    rejects_null: bool
    interpretation: str
    warnings: tuple[str, ...]


def run_ttest(
    series: pd.Series,
    *,
    popmean: float = 0.0,
    alternative: Alternative = "two-sided",
    significance: float = 0.05,
) -> TTestResult:
    """
    One-sample t-test: H0 mean equals ``popmean``.

    Assumes approximate normality or large n (CLT). For fat-tailed return
    series, prefer bootstrap_significance for robustness.
    """
    clean = _clean_series(series)
    stat, p_value = stats.ttest_1samp(clean.values, popmean, alternative=alternative)
    rejects = _reject(p_value, significance, alternative)

    assumptions = (
        "Observations treated as i.i.d. (serial correlation invalidates p-values).",
        "For small n or fat tails, t-test may be anti-conservative.",
    )

    if rejects:
        interp = (
            f"Reject H0: mean != {popmean} at {significance:.0%} "
            f"(t={stat:.3f}, p={p_value:.4f}, n={len(clean)})."
        )
    else:
        interp = (
            f"Fail to reject H0: mean={popmean} (t={stat:.3f}, p={p_value:.4f}). "
            "Absence of significance is not evidence of no effect."
        )
        if p_value > 0.10:
            logger.warning("t-test: weak significance (p=%.4f)", p_value)

    return TTestResult(
        statistic=float(stat),
        p_value=float(p_value),
        mean=float(clean.mean()),
        std=float(clean.std(ddof=1)),
        n_obs=len(clean),
        alternative=alternative,
        rejects_null=rejects,
        interpretation=interp,
        assumptions=assumptions,
    )


def confidence_interval(
    series: pd.Series,
    *,
    confidence: float = 0.95,
    method: Literal["t", "bootstrap"] = "t",
    n_bootstrap: int = 5000,
    rng: np.random.Generator | None = None,
) -> ConfidenceIntervalResult:
    """
    Confidence interval for the sample mean.

    ``t``: parametric using Student-t quantiles.
    ``bootstrap``: percentile bootstrap (i.i.d. resampling).
    """
    clean = _clean_series(series)
    mean = float(clean.mean())
    alpha = 1 - confidence

    if method == "t":
        se = float(clean.std(ddof=1) / np.sqrt(len(clean)))
        t_crit = float(stats.t.ppf(1 - alpha / 2, df=len(clean) - 1))
        lower = mean - t_crit * se
        upper = mean + t_crit * se
        method_label = "Student-t (i.i.d. assumption)"
    else:
        rng = rng or np.random.default_rng(42)
        boots = np.array(
            [float(rng.choice(clean.values, size=len(clean), replace=True).mean()) for _ in range(n_bootstrap)]
        )
        lower = float(np.percentile(boots, 100 * alpha / 2))
        upper = float(np.percentile(boots, 100 * (1 - alpha / 2)))
        method_label = f"Percentile bootstrap (n={n_bootstrap})"

    interp = (
        f"{confidence:.0%} CI for mean: [{lower:.6f}, {upper:.6f}]. "
        f"Point estimate={mean:.6f}."
    )

    return ConfidenceIntervalResult(
        point_estimate=mean,
        lower=lower,
        upper=upper,
        confidence_level=confidence,
        method=method_label,
        interpretation=interp,
    )


def bootstrap_significance(
    series: pd.Series,
    *,
    statistic_fn: Callable[[np.ndarray], float] | None = None,
    null_value: float = 0.0,
    n_bootstrap: int = 5000,
    confidence: float = 0.95,
    alternative: Alternative = "two-sided",
    significance: float = 0.05,
    rng: np.random.Generator | None = None,
) -> BootstrapSignificanceResult:
    """
    Bootstrap test for whether a statistic differs from ``null_value``.

    Default statistic is the sample mean. Uses i.i.d. resampling; for
    serially correlated returns, consider block bootstrap in production.
    """
    clean = _clean_series(series)
    rng = rng or np.random.default_rng(42)
    stat_fn = statistic_fn or (lambda x: float(np.mean(x)))
    observed = stat_fn(clean.values)

    centered = clean.values - float(np.mean(clean.values)) + null_value
    boot_stats = np.array(
        [stat_fn(rng.choice(centered, size=len(centered), replace=True)) for _ in range(n_bootstrap)]
    )

    if alternative == "two-sided":
        p_value = float(np.mean(np.abs(boot_stats - null_value) >= abs(observed - null_value)))
    elif alternative == "greater":
        p_value = float(np.mean(boot_stats >= observed))
    else:
        p_value = float(np.mean(boot_stats <= observed))

    rejects = p_value < significance
    alpha = 1 - confidence
    lower = float(np.percentile(boot_stats, 100 * alpha / 2))
    upper = float(np.percentile(boot_stats, 100 * (1 - alpha / 2)))

    ci = ConfidenceIntervalResult(
        point_estimate=observed,
        lower=lower,
        upper=upper,
        confidence_level=confidence,
        method=f"Bootstrap percentile (n={n_bootstrap})",
        interpretation=f"Bootstrap {confidence:.0%} CI: [{lower:.6f}, {upper:.6f}]",
    )

    warnings: list[str] = []
    if len(clean) < 30:
        warnings.append("Small sample: bootstrap inference may be unstable.")
    warnings.append("i.i.d. bootstrap ignores serial correlation in returns.")

    if rejects:
        interp = f"Reject H0: statistic != {null_value} (p={p_value:.4f}, boot n={n_bootstrap})."
    else:
        interp = f"Fail to reject H0 (p={p_value:.4f}). Statistic may not differ from {null_value}."
        if p_value > 0.10:
            logger.warning("Bootstrap: weak significance (p=%.4f)", p_value)

    return BootstrapSignificanceResult(
        observed_statistic=observed,
        bootstrap_mean=float(boot_stats.mean()),
        bootstrap_std=float(boot_stats.std(ddof=1)),
        p_value=p_value,
        confidence_interval=ci,
        n_bootstrap=n_bootstrap,
        rejects_null=rejects,
        interpretation=interp,
        warnings=tuple(warnings),
    )


def _reject(p_value: float, significance: float, alternative: Alternative) -> bool:
    return p_value < significance


def _clean_series(series: pd.Series) -> pd.Series:
    s = pd.Series(series).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) < 2:
        raise ValueError("Need at least 2 observations for hypothesis testing")
    return s
