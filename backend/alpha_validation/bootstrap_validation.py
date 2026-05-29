"""
Bootstrap validation for strategy return robustness.

Detects fragile Sharpe/expectancy estimates that may reflect overfitting
rather than persistent edge. Uses i.i.d. resampling by default.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from statistical_testing.hypothesis_tests import ConfidenceIntervalResult

logger = logging.getLogger(__name__)

TRADING_DAYS = 252.0


@dataclass(frozen=True)
class BootstrapValidationConfig:
    n_bootstrap: int = 5000
    confidence: float = 0.95
    risk_free_rate: float = 0.02
    rng_seed: int = 42


@dataclass(frozen=True)
class MetricBootstrapResult:
    metric_name: str
    observed: float
    bootstrap_mean: float
    bootstrap_std: float
    ci_lower: float
    ci_upper: float
    p_value_vs_zero: float
    is_robust: bool
    interpretation: str


@dataclass(frozen=True)
class BootstrapValidationResult:
    n_obs: int
    sharpe: MetricBootstrapResult
    expectancy: MetricBootstrapResult
    hit_rate: MetricBootstrapResult
    summary: str
    warnings: tuple[str, ...]


def run_bootstrap_validation(
    returns: pd.Series,
    *,
    config: BootstrapValidationConfig | None = None,
) -> BootstrapValidationResult:
    """
    Bootstrap Sharpe, expectancy, and hit-rate robustness for strategy returns.

    Parameters
    ----------
    returns : pd.Series
        Per-period strategy returns (not prices). Must be causal/OOS.
    """
    cfg = config or BootstrapValidationConfig()
    clean = _clean_returns(returns)
    rng = np.random.default_rng(cfg.rng_seed)
    warnings: list[str] = []

    if len(clean) < 30:
        warnings.append("Sample size < 30: bootstrap CIs may be unreliable.")

    warnings.append(
        "i.i.d. bootstrap assumes exchangeable returns. "
        "Serial correlation inflates false confidence — use block bootstrap for production."
    )

    sharpe = _bootstrap_metric(
        clean,
        metric_name="sharpe_ratio",
        stat_fn=lambda x: _sharpe(x, cfg.risk_free_rate),
        rng=rng,
        n_bootstrap=cfg.n_bootstrap,
        confidence=cfg.confidence,
    )
    expectancy = _bootstrap_metric(
        clean,
        metric_name="expectancy",
        stat_fn=lambda x: float(np.mean(x)),
        rng=rng,
        n_bootstrap=cfg.n_bootstrap,
        confidence=cfg.confidence,
    )
    hit_rate = _bootstrap_metric(
        clean,
        metric_name="hit_rate",
        stat_fn=lambda x: float(np.mean(x > 0)),
        rng=rng,
        n_bootstrap=cfg.n_bootstrap,
        confidence=cfg.confidence,
    )

    robust_count = sum(m.is_robust for m in (sharpe, expectancy, hit_rate))
    if robust_count < 2:
        summary = (
            f"Fragile alpha profile: only {robust_count}/3 metrics robust at "
            f"{cfg.confidence:.0%} (CI excludes zero / uninformative threshold)."
        )
        logger.warning(summary)
    else:
        summary = f"Moderate robustness: {robust_count}/3 metrics pass bootstrap checks."

    return BootstrapValidationResult(
        n_obs=len(clean),
        sharpe=sharpe,
        expectancy=expectancy,
        hit_rate=hit_rate,
        summary=summary,
        warnings=tuple(warnings),
    )


def _bootstrap_metric(
    returns: pd.Series,
    *,
    metric_name: str,
    stat_fn: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    n_bootstrap: int,
    confidence: float,
) -> MetricBootstrapResult:
    values = returns.values
    observed = stat_fn(values)
    boots = np.array(
        [stat_fn(rng.choice(values, size=len(values), replace=True)) for _ in range(n_bootstrap)]
    )

    alpha = 1 - confidence
    ci_lower = float(np.percentile(boots, 100 * alpha / 2))
    ci_upper = float(np.percentile(boots, 100 * (1 - alpha / 2)))
    p_value = float(np.mean(boots <= 0)) if observed > 0 else float(np.mean(boots >= 0))

    threshold = 0.0 if metric_name != "hit_rate" else 0.5
    is_robust = ci_lower > threshold if metric_name != "hit_rate" else ci_lower > 0.5

    if is_robust:
        interp = f"{metric_name}={observed:.4f} robust; {confidence:.0%} CI [{ci_lower:.4f}, {ci_upper:.4f}]."
    else:
        interp = (
            f"{metric_name}={observed:.4f} fragile; CI [{ci_lower:.4f}, {ci_upper:.4f}] "
            "includes uninformative region."
        )
        logger.warning("Bootstrap: %s not robust", metric_name)

    return MetricBootstrapResult(
        metric_name=metric_name,
        observed=observed,
        bootstrap_mean=float(boots.mean()),
        bootstrap_std=float(boots.std(ddof=1)),
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        p_value_vs_zero=p_value,
        is_robust=is_robust,
        interpretation=interp,
    )


def _sharpe(returns: np.ndarray, risk_free_rate: float) -> float:
    if len(returns) < 2 or returns.std(ddof=1) == 0:
        return 0.0
    excess = returns - risk_free_rate / TRADING_DAYS
    return float(excess.mean() / returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def _clean_returns(returns: pd.Series) -> pd.Series:
    s = pd.Series(returns).astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if len(s) < 5:
        raise ValueError("Need at least 5 return observations for bootstrap validation")
    return s
