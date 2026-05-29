"""
Regime-switching Monte Carlo — captures non-stationarity in return dynamics.

Real markets switch between regimes (trending, mean-reverting, crisis).
Each regime has different return distribution parameters. Simulating
from a mixture that switches between regimes produces more realistic
paths than a single Gaussian.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegimeParameters:
    """Return distribution parameters for a single regime."""

    name: str
    mean: float
    std: float
    skew: float = 0.0
    excess_kurtosis: float = 0.0


@dataclass(frozen=True)
class RegimeSwitchingConfig:
    """
    Configuration for regime-switching Monte Carlo.

    transition_matrix[i][j] = probability of switching from regime i to regime j.
    """

    regimes: tuple[RegimeParameters, ...] = (
        RegimeParameters(name="bull", mean=0.0005, std=0.01),
        RegimeParameters(name="bear", mean=-0.0003, std=0.018),
        RegimeParameters(name="crisis", mean=-0.002, std=0.035),
    )
    transition_matrix: tuple[tuple[float, ...], ...] = (
        (0.95, 0.03, 0.02),
        (0.05, 0.90, 0.05),
        (0.10, 0.15, 0.75),
    )
    n_simulations: int = 1000
    path_length: int = 252
    seed: int | None = 42


@dataclass(frozen=True)
class RegimeSwitchingResult:
    """Results from regime-switching Monte Carlo."""

    simulated_paths: np.ndarray
    terminal_values: np.ndarray
    regime_paths: np.ndarray
    mean_terminal: float
    median_terminal: float
    ci_5: float
    ci_95: float
    prob_loss: float
    mean_time_in_crisis: float
    worst_drawdown_distribution: np.ndarray


def fit_regime_parameters(
    returns: pd.Series,
    regime_labels: pd.Series,
) -> tuple[RegimeParameters, ...]:
    """Estimate regime parameters from labeled return data."""
    params = []
    for label in sorted(regime_labels.unique()):
        mask = regime_labels == label
        r = returns[mask].dropna()
        if len(r) < 10:
            continue
        params.append(
            RegimeParameters(
                name=str(label),
                mean=float(r.mean()),
                std=float(r.std()),
                skew=float(r.skew()),
                excess_kurtosis=float(r.kurtosis()),
            )
        )
    return tuple(params)


def run_regime_switching_mc(
    config: RegimeSwitchingConfig | None = None,
) -> RegimeSwitchingResult:
    """
    Generate Monte Carlo paths with Markov regime switching.

    Each step:
    1. Sample next regime from transition matrix
    2. Draw return from that regime's distribution
    """
    cfg = config or RegimeSwitchingConfig()
    rng = np.random.default_rng(cfg.seed)

    n_regimes = len(cfg.regimes)
    trans = np.array(cfg.transition_matrix)

    for i in range(n_regimes):
        row_sum = trans[i].sum()
        if abs(row_sum - 1.0) > 1e-6:
            raise ValueError(f"Transition matrix row {i} sums to {row_sum}, not 1.0")

    paths = np.ones((cfg.n_simulations, cfg.path_length + 1))
    regime_paths = np.zeros((cfg.n_simulations, cfg.path_length), dtype=int)

    for sim in range(cfg.n_simulations):
        current_regime = rng.choice(n_regimes)
        for t in range(cfg.path_length):
            current_regime = rng.choice(n_regimes, p=trans[current_regime])
            regime_paths[sim, t] = current_regime
            rp = cfg.regimes[current_regime]
            ret = rng.normal(rp.mean, rp.std)
            paths[sim, t + 1] = paths[sim, t] * (1 + ret)

    terminal = paths[:, -1]
    running_max = np.maximum.accumulate(paths, axis=1)
    drawdowns = (paths - running_max) / np.maximum(running_max, 1e-9)
    worst_dds = drawdowns.min(axis=1)

    crisis_idx = next(
        (i for i, r in enumerate(cfg.regimes) if "crisis" in r.name.lower()),
        n_regimes - 1,
    )
    crisis_time = np.mean(regime_paths == crisis_idx, axis=1)

    return RegimeSwitchingResult(
        simulated_paths=paths,
        terminal_values=terminal,
        regime_paths=regime_paths,
        mean_terminal=float(np.mean(terminal)),
        median_terminal=float(np.median(terminal)),
        ci_5=float(np.percentile(terminal, 5)),
        ci_95=float(np.percentile(terminal, 95)),
        prob_loss=float(np.mean(terminal < 1.0)),
        mean_time_in_crisis=float(np.mean(crisis_time)),
        worst_drawdown_distribution=worst_dds,
    )
