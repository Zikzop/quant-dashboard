"""
Block bootstrap — preserves autocorrelation and volatility clustering.

Standard IID bootstrap destroys serial dependence in return series.
Block bootstrap resamples contiguous blocks, preserving:
- volatility clustering (GARCH effects)
- momentum/mean-reversion persistence
- cross-sectional correlation structure within blocks

This is the minimum viable bootstrap for financial time series.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BlockBootstrapConfig:
    """
    Configuration for block bootstrap.

    block_size : int
        Length of contiguous blocks. Should be large enough to capture
        autocorrelation decay (~20 trading days is common).
    n_simulations : int
        Number of bootstrap paths.
    """

    block_size: int = 21
    n_simulations: int = 1000
    seed: int | None = 42


@dataclass(frozen=True)
class BlockBootstrapResult:
    """Bootstrap simulation results with confidence intervals."""

    simulated_terminal_values: np.ndarray
    simulated_sharpe_ratios: np.ndarray
    simulated_max_drawdowns: np.ndarray
    mean_terminal: float
    median_terminal: float
    ci_5: float
    ci_95: float
    prob_loss: float
    mean_sharpe: float
    median_sharpe: float
    sharpe_ci_5: float
    sharpe_ci_95: float
    mean_max_dd: float
    worst_max_dd: float


def run_block_bootstrap(
    returns: pd.Series,
    config: BlockBootstrapConfig | None = None,
) -> BlockBootstrapResult:
    """
    Run block bootstrap simulation on a return series.

    Preserves autocorrelation structure by resampling contiguous blocks
    rather than individual observations.
    """
    cfg = config or BlockBootstrapConfig()
    rng = np.random.default_rng(cfg.seed)
    r = returns.dropna().values
    n = len(r)

    if n < cfg.block_size * 2:
        raise ValueError(
            f"Return series ({n} obs) too short for block_size={cfg.block_size}"
        )

    n_blocks = int(np.ceil(n / cfg.block_size))
    max_start = n - cfg.block_size

    terminal_values = np.empty(cfg.n_simulations)
    sharpe_ratios = np.empty(cfg.n_simulations)
    max_drawdowns = np.empty(cfg.n_simulations)

    for i in range(cfg.n_simulations):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        blocks = [r[s : s + cfg.block_size] for s in starts]
        sim_returns = np.concatenate(blocks)[:n]

        equity = np.cumprod(1.0 + sim_returns)
        terminal_values[i] = equity[-1]

        mean_r = np.mean(sim_returns)
        std_r = np.std(sim_returns, ddof=1)
        sharpe_ratios[i] = mean_r / max(std_r, 1e-9) * np.sqrt(252)

        running_max = np.maximum.accumulate(equity)
        drawdowns = (equity - running_max) / np.maximum(running_max, 1e-9)
        max_drawdowns[i] = float(np.min(drawdowns))

    return BlockBootstrapResult(
        simulated_terminal_values=terminal_values,
        simulated_sharpe_ratios=sharpe_ratios,
        simulated_max_drawdowns=max_drawdowns,
        mean_terminal=float(np.mean(terminal_values)),
        median_terminal=float(np.median(terminal_values)),
        ci_5=float(np.percentile(terminal_values, 5)),
        ci_95=float(np.percentile(terminal_values, 95)),
        prob_loss=float(np.mean(terminal_values < 1.0)),
        mean_sharpe=float(np.mean(sharpe_ratios)),
        median_sharpe=float(np.median(sharpe_ratios)),
        sharpe_ci_5=float(np.percentile(sharpe_ratios, 5)),
        sharpe_ci_95=float(np.percentile(sharpe_ratios, 95)),
        mean_max_dd=float(np.mean(max_drawdowns)),
        worst_max_dd=float(np.min(max_drawdowns)),
    )
