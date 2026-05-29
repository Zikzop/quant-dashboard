"""
Conditional VaR (CVaR / Expected Shortfall) — what happens BEYOND VaR.

CVaR answers the question VaR ignores: "When we do lose more than VaR,
how bad is it?" This is the expected loss conditional on exceeding the
VaR threshold.

CVaR is a coherent risk measure (satisfies subadditivity), making it
superior to VaR for portfolio risk aggregation. Basel III/IV requires
Expected Shortfall for internal models.

STILL LIMITED: CVaR remains a statistical summary that assumes
stationarity. During regime shifts, both VaR and CVaR break down.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_engine.risk_config import VaRConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CVaRResult:
    """CVaR computation results with diagnostic detail."""

    cvar_levels: dict[float, float]
    var_levels: dict[float, float]
    tail_ratio: dict[float, float]
    n_tail_observations: dict[float, int]
    worst_loss: float
    tail_mean: float
    tail_std: float
    n_observations: int


class CVaREngine:
    """
    Computes CVaR (Expected Shortfall) from historical returns.

    Also computes the tail ratio: CVaR / VaR, which measures how much
    worse the tail is than the VaR threshold suggests. A ratio significantly
    above 1.0 indicates dangerous tail convexity.
    """

    def __init__(self, config: VaRConfig | None = None) -> None:
        self._config = config or VaRConfig()

    def compute(
        self,
        returns: pd.Series,
        confidence_levels: tuple[float, ...] | None = None,
    ) -> CVaRResult:
        levels = confidence_levels or self._config.confidence_levels
        r = returns.dropna().iloc[-self._config.lookback_days:]

        if len(r) < self._config.min_observations:
            empty = {cl: 0.0 for cl in levels}
            return CVaRResult(
                cvar_levels=empty,
                var_levels=empty,
                tail_ratio=empty,
                n_tail_observations={cl: 0 for cl in levels},
                worst_loss=0.0,
                tail_mean=0.0,
                tail_std=0.0,
                n_observations=len(r),
            )

        r_arr = r.values
        var_levels = {}
        cvar_levels = {}
        tail_ratios = {}
        n_tail = {}

        for cl in levels:
            q = np.percentile(r_arr, (1.0 - cl) * 100)
            var_levels[cl] = float(q)

            tail = r_arr[r_arr <= q]
            n_tail[cl] = len(tail)
            cvar = float(np.mean(tail)) if len(tail) > 0 else float(q)
            cvar_levels[cl] = cvar

            tail_ratios[cl] = cvar / min(q, -1e-9) if q < 0 else 1.0

        all_tail = r_arr[r_arr <= np.percentile(r_arr, 5)]

        return CVaRResult(
            cvar_levels=cvar_levels,
            var_levels=var_levels,
            tail_ratio=tail_ratios,
            n_tail_observations=n_tail,
            worst_loss=float(r_arr.min()),
            tail_mean=float(np.mean(all_tail)) if len(all_tail) > 0 else 0.0,
            tail_std=float(np.std(all_tail)) if len(all_tail) > 1 else 0.0,
            n_observations=len(r),
        )
