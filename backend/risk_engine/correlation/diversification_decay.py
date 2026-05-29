"""
Diversification decay — tracking how diversification erodes over time.

The diversification ratio = sum of individual volatilities / portfolio volatility.
A ratio of 2.0 means the portfolio has half the vol that an undiversified
equally-vol-weighted version would have.

During crises, the diversification ratio collapses toward 1.0 as
correlations surge. Monitoring the trend reveals whether diversification
is genuine or illusory.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiversificationState:
    """Diversification quality assessment."""

    diversification_ratio: float
    effective_n_assets: float
    marginal_diversification: dict[str, float]
    diversification_trend: float
    is_decaying: bool
    decay_speed: float


class DiversificationDecayMonitor:
    """
    Tracks the diversification ratio and its trend over time.

    Also computes marginal diversification: the risk reduction from adding
    or removing each position, revealing which positions are genuinely
    diversifying vs. redundant.
    """

    def __init__(self, lookback_days: int = 63) -> None:
        self._lookback = lookback_days
        self._ratio_history: list[float] = []

    def assess(
        self,
        returns: pd.DataFrame,
        weights: dict[str, float] | None = None,
    ) -> DiversificationState:
        if returns.shape[1] < 2 or len(returns) < 20:
            return DiversificationState(
                diversification_ratio=1.0,
                effective_n_assets=returns.shape[1],
                marginal_diversification={},
                diversification_trend=0.0,
                is_decaying=False,
                decay_speed=0.0,
            )

        recent = returns.iloc[-self._lookback:]
        cols = recent.columns.tolist()
        n = len(cols)

        if weights:
            w = np.array([weights.get(c, 1.0 / n) for c in cols])
        else:
            w = np.ones(n) / n

        individual_vols = recent.std().values
        weighted_vol_sum = float(np.sum(np.abs(w) * individual_vols))

        cov = recent.cov().values
        port_var = float(w @ cov @ w)
        port_vol = np.sqrt(max(port_var, 1e-12))

        div_ratio = weighted_vol_sum / max(port_vol, 1e-9)
        self._ratio_history.append(div_ratio)

        effective_n = div_ratio ** 2

        marginal = {}
        for i, col in enumerate(cols):
            w_ex = w.copy()
            w_ex[i] = 0.0
            w_sum = np.sum(np.abs(w_ex))
            if w_sum > 0:
                w_ex = w_ex / w_sum * np.sum(np.abs(w))
            port_var_ex = float(w_ex @ cov @ w_ex)
            port_vol_ex = np.sqrt(max(port_var_ex, 1e-12))
            marginal[col] = float(port_vol - port_vol_ex)

        if len(self._ratio_history) >= 5:
            recent_ratios = np.array(self._ratio_history[-20:])
            if len(recent_ratios) >= 5:
                x = np.arange(len(recent_ratios))
                slope = float(np.polyfit(x, recent_ratios, 1)[0])
            else:
                slope = 0.0
        else:
            slope = 0.0

        is_decaying = slope < -0.01 and len(self._ratio_history) >= 5
        decay_speed = max(0.0, -slope)

        return DiversificationState(
            diversification_ratio=div_ratio,
            effective_n_assets=effective_n,
            marginal_diversification=marginal,
            diversification_trend=slope,
            is_decaying=is_decaying,
            decay_speed=decay_speed,
        )
