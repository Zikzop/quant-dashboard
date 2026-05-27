"""
Tail risk estimation — beyond VaR and CVaR.

Financial returns exhibit fat tails that Gaussian and even Student-t
models underestimate for extreme quantiles. This module uses:
- Hill estimator for tail index (how fat is the tail?)
- Peak-over-threshold (POT) for extreme value estimation
- Tail concentration measures

A tail index < 2 means infinite variance; < 3 means infinite skewness.
Most equity return series have tail indices between 2.5 and 4.5,
indicating variance exists but extreme events are far more likely
than Gaussian models predict.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TailRiskEstimate:
    """Tail risk diagnostic output."""

    hill_estimator: float
    tail_index: float
    tail_is_fat: bool
    extreme_loss_probability: float
    expected_extreme_loss: float
    n_tail_observations: int
    pot_threshold: float
    max_observed_loss: float
    tail_asymmetry: float


class TailRiskEngine:
    """
    Estimates tail risk properties from return data.

    The Hill estimator is the workhorse: it estimates the tail index α
    from the largest losses. α determines how fast the tail decays:
    - α > 4: mild tails (Gaussian-like)
    - 3 < α < 4: moderate fat tails
    - 2 < α < 3: heavy tails (infinite kurtosis)
    - α ≤ 2: extremely heavy tails (infinite variance)
    """

    def __init__(self, tail_fraction: float = 0.10) -> None:
        self._tail_fraction = tail_fraction

    def estimate(self, returns: pd.Series) -> TailRiskEstimate:
        r = returns.dropna().values

        if len(r) < 30:
            return self._empty_estimate()

        losses = -r[r < 0]
        if len(losses) < 10:
            return self._empty_estimate()

        k = max(10, int(len(losses) * self._tail_fraction))
        sorted_losses = np.sort(losses)[::-1]
        top_k = sorted_losses[:k]
        threshold = sorted_losses[k - 1]

        if threshold <= 0:
            return self._empty_estimate()

        hill = float(np.mean(np.log(top_k / threshold)))
        hill = max(hill, 1e-6)
        tail_index = 1.0 / hill

        gains = r[r > 0]
        if len(gains) >= 10:
            k_g = max(10, int(len(gains) * self._tail_fraction))
            sorted_gains = np.sort(gains)[::-1]
            top_k_g = sorted_gains[:k_g]
            threshold_g = sorted_gains[k_g - 1]
            if threshold_g > 0:
                hill_g = float(np.mean(np.log(top_k_g / threshold_g)))
                tail_index_g = 1.0 / max(hill_g, 1e-6)
            else:
                tail_index_g = tail_index
        else:
            tail_index_g = tail_index

        asymmetry = tail_index_g / max(tail_index, 1e-6)

        extreme_prob = float(k / len(losses) * (2 * threshold / threshold) ** (-tail_index))
        extreme_prob = min(extreme_prob, 1.0)
        expected_extreme = float(threshold * tail_index / max(tail_index - 1, 0.1))

        return TailRiskEstimate(
            hill_estimator=hill,
            tail_index=tail_index,
            tail_is_fat=tail_index < 4.0,
            extreme_loss_probability=extreme_prob,
            expected_extreme_loss=expected_extreme,
            n_tail_observations=k,
            pot_threshold=float(threshold),
            max_observed_loss=float(sorted_losses[0]) if len(sorted_losses) > 0 else 0.0,
            tail_asymmetry=asymmetry,
        )

    @staticmethod
    def _empty_estimate() -> TailRiskEstimate:
        return TailRiskEstimate(
            hill_estimator=0.0,
            tail_index=0.0,
            tail_is_fat=False,
            extreme_loss_probability=0.0,
            expected_extreme_loss=0.0,
            n_tail_observations=0,
            pot_threshold=0.0,
            max_observed_loss=0.0,
            tail_asymmetry=1.0,
        )
