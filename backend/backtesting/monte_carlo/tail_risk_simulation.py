"""
Tail risk simulation — models extreme events that Gaussian distributions miss.

Financial returns have fat tails: extreme events occur far more often
than a normal distribution predicts. Using Student-t or stable distributions
captures this. Ignoring tail risk leads to catastrophic underestimation
of drawdown severity and frequency.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TailRiskConfig:
    """
    Tail risk simulation configuration.

    df : float
        Degrees of freedom for Student-t distribution.
        Lower = fatter tails. df=3-5 is typical for daily equity returns.
    """

    n_simulations: int = 1000
    path_length: int = 252
    df: float = 4.0
    seed: int | None = 42


@dataclass(frozen=True)
class TailRiskResult:
    """Tail risk simulation results."""

    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    max_loss_1day: float
    prob_5pct_loss: float
    prob_10pct_loss: float
    prob_20pct_loss: float
    tail_index: float
    terminal_values: np.ndarray
    worst_drawdowns: np.ndarray


def estimate_tail_index(returns: pd.Series) -> float:
    """
    Hill estimator for the tail index of the return distribution.

    A tail index < 4 means infinite kurtosis (extremely fat tails).
    A tail index < 2 means infinite variance (dangerously heavy tails).
    """
    r = np.abs(returns.dropna().values)
    r = r[r > 0]
    r.sort()
    n = len(r)
    if n < 50:
        return float("nan")
    k = max(10, int(n * 0.05))
    threshold = r[-k]
    exceedances = r[r >= threshold]
    log_ratios = np.log(exceedances / threshold)
    return float(k / np.sum(log_ratios)) if np.sum(log_ratios) > 0 else float("nan")


def run_tail_risk_simulation(
    returns: pd.Series,
    config: TailRiskConfig | None = None,
) -> TailRiskResult:
    """
    Simulate return paths using fitted Student-t distribution.

    Captures fat tails, which Gaussian Monte Carlo misses entirely.
    """
    cfg = config or TailRiskConfig()
    rng = np.random.default_rng(cfg.seed)
    r = returns.dropna().values
    n = len(r)

    mu = np.mean(r)
    sigma = np.std(r, ddof=1)

    try:
        df_fit, loc_fit, scale_fit = stats.t.fit(r)
        df_fit = max(2.1, min(df_fit, 30))
    except Exception:
        df_fit, loc_fit, scale_fit = cfg.df, mu, sigma

    paths = np.ones((cfg.n_simulations, cfg.path_length + 1))
    for sim in range(cfg.n_simulations):
        innovations = stats.t.rvs(
            df_fit, loc=loc_fit, scale=scale_fit, size=cfg.path_length,
            random_state=rng.integers(0, 2**31),
        )
        paths[sim, 1:] = np.cumprod(1 + innovations)

    terminal = paths[:, -1]
    daily_returns_all = np.diff(paths, axis=1) / np.maximum(paths[:, :-1], 1e-9)
    flat_returns = daily_returns_all.flatten()

    running_max = np.maximum.accumulate(paths, axis=1)
    drawdowns = (paths - running_max) / np.maximum(running_max, 1e-9)
    worst_dds = drawdowns.min(axis=1)

    var_95 = float(np.percentile(flat_returns, 5))
    var_99 = float(np.percentile(flat_returns, 1))
    tail_5 = flat_returns[flat_returns <= var_95]
    tail_1 = flat_returns[flat_returns <= var_99]
    cvar_95 = float(np.mean(tail_5)) if len(tail_5) > 0 else var_95
    cvar_99 = float(np.mean(tail_1)) if len(tail_1) > 0 else var_99

    return TailRiskResult(
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        cvar_99=cvar_99,
        max_loss_1day=float(np.min(flat_returns)),
        prob_5pct_loss=float(np.mean(terminal < 0.95)),
        prob_10pct_loss=float(np.mean(terminal < 0.90)),
        prob_20pct_loss=float(np.mean(terminal < 0.80)),
        tail_index=estimate_tail_index(returns),
        terminal_values=terminal,
        worst_drawdowns=worst_dds,
    )
