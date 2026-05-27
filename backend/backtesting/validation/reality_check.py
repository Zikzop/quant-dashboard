"""
White's Reality Check and Hansen's Superior Predictive Ability test.

Tests whether the best strategy from a universe of strategies has
genuine predictive ability, or whether its performance is just the
maximum of many noise processes.

Reference:
- White (2000), "A Reality Check for Data Snooping"
- Hansen (2005), "A Test for Superior Predictive Ability"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RealityCheckConfig:
    """Configuration for the reality check bootstrap."""

    n_bootstrap: int = 1000
    block_size: int = 21
    seed: int | None = 42


@dataclass(frozen=True)
class RealityCheckResult:
    """Reality check test result."""

    best_strategy_idx: int
    best_strategy_sharpe: float
    p_value: float
    is_significant: bool
    bootstrap_distribution: np.ndarray
    n_strategies: int
    warnings: tuple[str, ...]


def whites_reality_check(
    strategy_returns: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
    config: RealityCheckConfig | None = None,
) -> RealityCheckResult:
    """
    White's Reality Check for data snooping.

    Tests the null hypothesis that the best strategy has no genuine
    predictive ability beyond what's expected from the maximum of
    n_strategies random processes.

    strategy_returns : DataFrame
        Each column is a strategy's return series.
    benchmark_returns : Series or None
        If provided, test excess returns over benchmark.
    """
    cfg = config or RealityCheckConfig()
    rng = np.random.default_rng(cfg.seed)

    if benchmark_returns is not None:
        excess = strategy_returns.subtract(benchmark_returns, axis=0)
    else:
        excess = strategy_returns.copy()

    excess = excess.dropna()
    R = excess.values
    n_obs, n_strats = R.shape

    mean_excess = R.mean(axis=0)
    best_idx = int(np.argmax(mean_excess))
    best_mean = float(mean_excess[best_idx])
    observed_stat = best_mean * np.sqrt(n_obs)

    max_start = n_obs - cfg.block_size
    if max_start <= 0:
        raise ValueError("Return series too short for block bootstrap")

    n_blocks = int(np.ceil(n_obs / cfg.block_size))
    boot_stats = np.empty(cfg.n_bootstrap)

    for b in range(cfg.n_bootstrap):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        boot_indices = np.concatenate(
            [np.arange(s, min(s + cfg.block_size, n_obs)) for s in starts]
        )[:n_obs]

        R_boot = R[boot_indices]
        centered = R_boot - R_boot.mean(axis=0)
        boot_means = centered.mean(axis=0)
        boot_stats[b] = np.max(boot_means) * np.sqrt(n_obs)

    p_value = float(np.mean(boot_stats >= observed_stat))

    warnings: list[str] = []
    if p_value > 0.05:
        warnings.append(
            f"Reality Check FAILS (p={p_value:.4f}). Best strategy's performance "
            f"is consistent with data snooping across {n_strats} strategies."
        )
    if n_strats > 100:
        warnings.append(
            f"Testing {n_strats} strategies severely inflates false discovery risk"
        )

    return RealityCheckResult(
        best_strategy_idx=best_idx,
        best_strategy_sharpe=float(mean_excess[best_idx] / max(R[:, best_idx].std(), 1e-9) * np.sqrt(252)),
        p_value=p_value,
        is_significant=p_value < 0.05,
        bootstrap_distribution=boot_stats,
        n_strategies=n_strats,
        warnings=tuple(warnings),
    )
