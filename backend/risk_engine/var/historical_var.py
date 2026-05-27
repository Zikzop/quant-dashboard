"""
Historical VaR — non-parametric quantile estimation from realized returns.

Historical VaR makes no distributional assumptions: it simply takes
the empirical quantile of observed returns. This captures the actual
tail shape including fat tails and skewness.

LIMITATIONS:
- Backward-looking: future may not resemble the past
- Sample-dependent: sensitive to the lookback window
- Cannot extrapolate beyond observed extremes
- Ignores time-varying volatility unless windowed appropriately
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_engine.risk_config import VaRConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HistoricalVaRResult:
    """Historical VaR computation results."""

    var_levels: dict[float, float]
    n_observations: int
    lookback_days: int
    worst_loss: float
    mean_return: float
    vol_annualized: float


class HistoricalVaREngine:
    """
    Computes VaR from the empirical return distribution.

    Optionally applies exponential decay weighting to give more
    influence to recent observations, balancing between full-sample
    accuracy and regime responsiveness.
    """

    def __init__(self, config: VaRConfig | None = None) -> None:
        self._config = config or VaRConfig()

    def compute(
        self,
        returns: pd.Series,
        confidence_levels: tuple[float, ...] | None = None,
    ) -> HistoricalVaRResult:
        levels = confidence_levels or self._config.confidence_levels
        r = returns.dropna().iloc[-self._config.lookback_days:]

        if len(r) < self._config.min_observations:
            return HistoricalVaRResult(
                var_levels={cl: 0.0 for cl in levels},
                n_observations=len(r),
                lookback_days=self._config.lookback_days,
                worst_loss=float(r.min()) if len(r) > 0 else 0.0,
                mean_return=float(r.mean()) if len(r) > 0 else 0.0,
                vol_annualized=0.0,
            )

        if self._config.decay_factor < 1.0:
            weights = np.array([
                self._config.decay_factor ** i for i in range(len(r) - 1, -1, -1)
            ])
            weights /= weights.sum()
            sorted_idx = np.argsort(r.values)
            sorted_r = r.values[sorted_idx]
            sorted_w = weights[sorted_idx]
            cum_w = np.cumsum(sorted_w)
            var_levels = {}
            for cl in levels:
                threshold = 1.0 - cl
                idx = np.searchsorted(cum_w, threshold)
                idx = min(idx, len(sorted_r) - 1)
                var_levels[cl] = float(sorted_r[idx])
        else:
            var_levels = {}
            for cl in levels:
                var_levels[cl] = float(np.percentile(r, (1.0 - cl) * 100))

        return HistoricalVaRResult(
            var_levels=var_levels,
            n_observations=len(r),
            lookback_days=self._config.lookback_days,
            worst_loss=float(r.min()),
            mean_return=float(r.mean()),
            vol_annualized=float(r.std() * np.sqrt(252)),
        )
