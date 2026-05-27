"""
Monte Carlo VaR — simulation-based risk quantification.

Monte Carlo VaR generates thousands of forward-looking return paths
from a fitted distribution (Student-t with regime-dependent parameters)
and takes quantiles of the terminal distribution.

Advantages over historical VaR:
- Can generate paths beyond observed history
- Naturally incorporates fat tails via Student-t or mixture models
- Extensible to multivariate (correlated) simulations

LIMITATIONS:
- Only as good as the assumed distribution
- Computationally expensive for large portfolios
- Correlation assumptions dominate multi-asset results
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
class MonteCarloVaRResult:
    """Monte Carlo VaR results."""

    var_levels: dict[float, float]
    expected_shortfall: dict[float, float]
    mean_terminal: float
    median_terminal: float
    worst_path_loss: float
    prob_loss: float
    n_simulations: int
    path_length: int


class MonteCarloVaREngine:
    """
    Simulates forward return paths and computes VaR from the simulated distribution.

    Uses Student-t innovations fitted to historical returns, capturing
    fat tails without imposing Gaussian assumptions.
    """

    def __init__(self, config: VaRConfig | None = None) -> None:
        self._config = config or VaRConfig()

    def compute(
        self,
        returns: pd.Series,
        confidence_levels: tuple[float, ...] | None = None,
        seed: int | None = 42,
    ) -> MonteCarloVaRResult:
        levels = confidence_levels or self._config.confidence_levels
        r = returns.dropna().iloc[-self._config.lookback_days:]

        if len(r) < self._config.min_observations:
            empty = {cl: 0.0 for cl in levels}
            return MonteCarloVaRResult(
                var_levels=empty,
                expected_shortfall=empty,
                mean_terminal=0.0,
                median_terminal=0.0,
                worst_path_loss=0.0,
                prob_loss=0.0,
                n_simulations=0,
                path_length=0,
            )

        try:
            df_fit, loc_fit, scale_fit = sp_stats.t.fit(r)
            df_fit = max(2.1, min(df_fit, 100.0))
        except Exception:
            df_fit = 5.0
            loc_fit = float(r.mean())
            scale_fit = float(r.std())

        rng = np.random.default_rng(seed)
        n_sims = self._config.monte_carlo_simulations
        path_len = self._config.mc_path_length

        innovations = sp_stats.t.rvs(
            df=df_fit,
            loc=loc_fit,
            scale=scale_fit,
            size=(n_sims, path_len),
            random_state=rng.integers(0, 2**31),
        )

        paths = np.cumprod(1.0 + innovations, axis=1)
        terminal = paths[:, -1]
        terminal_returns = terminal - 1.0

        var_levels = {}
        es_levels = {}
        for cl in levels:
            q = np.percentile(terminal_returns, (1.0 - cl) * 100)
            var_levels[cl] = float(q)
            tail = terminal_returns[terminal_returns <= q]
            es_levels[cl] = float(np.mean(tail)) if len(tail) > 0 else float(q)

        return MonteCarloVaRResult(
            var_levels=var_levels,
            expected_shortfall=es_levels,
            mean_terminal=float(np.mean(terminal_returns)),
            median_terminal=float(np.median(terminal_returns)),
            worst_path_loss=float(np.min(terminal_returns)),
            prob_loss=float(np.mean(terminal_returns < 0)),
            n_simulations=n_sims,
            path_length=path_len,
        )
