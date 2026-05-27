"""
Deflated Sharpe ratio — adjusts for multiple testing and non-normality.

When you test N strategies and pick the best one, the expected maximum
Sharpe ratio grows with sqrt(log(N)) even if all strategies have zero
true alpha. The deflated Sharpe ratio corrects for this selection bias.

Reference: Bailey & Lopez de Prado, "The Deflated Sharpe Ratio" (2014).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeflatedSharpeResult:
    """Deflated Sharpe ratio test result."""

    observed_sharpe: float
    deflated_sharpe: float
    expected_max_sharpe: float
    p_value: float
    is_significant: bool
    n_trials: int
    skewness: float
    kurtosis: float
    t_statistic: float
    warnings: tuple[str, ...]


def expected_max_sharpe(
    n_trials: int,
    mean_sharpe: float = 0.0,
    std_sharpe: float = 1.0,
) -> float:
    """
    Expected maximum Sharpe ratio from n_trials independent strategies
    under the null hypothesis of zero true alpha.

    E[max(SR)] ≈ std * ((1 - gamma) * Phi^{-1}(1 - 1/N) + gamma * Phi^{-1}(1 - 1/(N*e)))
    Simplified: ≈ sqrt(2 * log(N)) - (log(pi) + log(log(N))) / (2 * sqrt(2 * log(N)))
    """
    if n_trials <= 1:
        return mean_sharpe

    z = np.sqrt(2.0 * np.log(n_trials))
    correction = (np.log(np.pi) + np.log(np.log(max(n_trials, 2)))) / (2.0 * z)
    return float(mean_sharpe + std_sharpe * (z - correction))


def compute_deflated_sharpe(
    observed_sharpe: float,
    n_observations: int,
    n_trials: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
    sharpe_std: float = 1.0,
) -> DeflatedSharpeResult:
    """
    Compute the deflated Sharpe ratio.

    Tests whether the observed Sharpe exceeds what would be expected
    by chance when selecting from n_trials strategies.
    """
    warnings: list[str] = []

    sr0 = expected_max_sharpe(n_trials, mean_sharpe=0.0, std_sharpe=sharpe_std)

    excess_kurtosis = kurtosis - 3.0
    sr_std = np.sqrt(
        (1.0 - skewness * observed_sharpe + (excess_kurtosis / 4.0) * observed_sharpe ** 2)
        / max(n_observations - 1, 1)
    )

    if sr_std < 1e-9:
        sr_std = 1e-9

    t_stat = (observed_sharpe - sr0) / sr_std

    p_value = float(1.0 - stats.norm.cdf(t_stat))
    deflated = observed_sharpe - sr0

    is_significant = p_value < 0.05

    if not is_significant:
        warnings.append(
            f"Deflated Sharpe test FAILS (p={p_value:.4f}). "
            f"Observed SR={observed_sharpe:.2f} does not exceed expected "
            f"maximum from {n_trials} trials (E[max]={sr0:.2f})."
        )
    if n_trials > 20:
        warnings.append(
            f"Testing {n_trials} strategies inflates expected max Sharpe to {sr0:.2f}"
        )
    if abs(skewness) > 1:
        warnings.append(f"Non-normal returns (skew={skewness:.2f}) affect Sharpe reliability")

    return DeflatedSharpeResult(
        observed_sharpe=observed_sharpe,
        deflated_sharpe=deflated,
        expected_max_sharpe=sr0,
        p_value=p_value,
        is_significant=is_significant,
        n_trials=n_trials,
        skewness=skewness,
        kurtosis=kurtosis,
        t_statistic=float(t_stat),
        warnings=tuple(warnings),
    )
