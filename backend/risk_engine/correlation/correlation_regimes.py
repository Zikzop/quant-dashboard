"""
Correlation regime detection — identifies structural shifts in correlation structure.

Correlations cluster into regimes:
- Low correlation (diversification works)
- Normal correlation (expected behavior)
- High correlation (crisis onset — diversification failing)
- Breakdown (near-unity correlations — no diversification)

Detecting the transition from normal to high-correlation regime early
gives the risk engine time to reduce exposure before diversification
fully evaporates.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_engine.risk_config import CorrelationConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorrelationRegimeState:
    """Current correlation regime classification."""

    regime: str
    mean_correlation: float
    regime_z_score: float
    regime_duration_days: int
    transition_probability: float
    is_transitioning: bool


class CorrelationRegimeDetector:
    """
    Detects correlation regime based on rolling average correlation.

    Uses a simple threshold-based classifier with hysteresis to prevent
    rapid regime flipping. The z-score of mean correlation relative to
    its long-term distribution provides a continuous regime signal.
    """

    def __init__(self, config: CorrelationConfig | None = None) -> None:
        self._config = config or CorrelationConfig()
        self._current_regime = "NORMAL"
        self._regime_start_idx = 0
        self._mean_corr_history: list[float] = []

    def detect(
        self,
        returns: pd.DataFrame,
        timestamp: pd.Timestamp | None = None,
    ) -> CorrelationRegimeState:
        if returns.shape[1] < 2 or len(returns) < self._config.rolling_window_days:
            return CorrelationRegimeState(
                regime="UNKNOWN",
                mean_correlation=0.0,
                regime_z_score=0.0,
                regime_duration_days=0,
                transition_probability=0.0,
                is_transitioning=False,
            )

        recent = returns.iloc[-self._config.rolling_window_days:]
        corr = recent.corr().values
        n = corr.shape[0]
        upper = corr[np.triu_indices(n, k=1)]
        mean_corr = float(np.mean(upper))
        self._mean_corr_history.append(mean_corr)

        if len(self._mean_corr_history) >= 20:
            hist = np.array(self._mean_corr_history)
            z = float((mean_corr - hist.mean()) / max(hist.std(), 1e-9))
        else:
            z = 0.0

        new_regime = self._classify(mean_corr, z)

        is_transitioning = new_regime != self._current_regime
        if is_transitioning:
            self._current_regime = new_regime
            self._regime_start_idx = len(self._mean_corr_history)

        duration = len(self._mean_corr_history) - self._regime_start_idx

        trans_prob = self._transition_probability(z)

        return CorrelationRegimeState(
            regime=self._current_regime,
            mean_correlation=mean_corr,
            regime_z_score=z,
            regime_duration_days=duration,
            transition_probability=trans_prob,
            is_transitioning=is_transitioning,
        )

    def _classify(self, mean_corr: float, z: float) -> str:
        threshold = self._config.regime_threshold
        if mean_corr > 0.8 or z > 3.0:
            return "BREAKDOWN"
        elif mean_corr > threshold + 0.2 or z > 2.0:
            return "HIGH"
        elif mean_corr > threshold:
            return "NORMAL"
        else:
            return "LOW"

    @staticmethod
    def _transition_probability(z: float) -> float:
        """Heuristic transition probability based on z-score."""
        abs_z = abs(z)
        if abs_z < 1.0:
            return 0.05
        elif abs_z < 2.0:
            return 0.20
        elif abs_z < 3.0:
            return 0.50
        else:
            return 0.80
