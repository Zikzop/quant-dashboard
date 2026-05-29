"""
Partial fill model — simulates realistic fill completeness.

Not all orders fill completely. This model determines what fraction
of the requested quantity gets executed based on market conditions.

Statistical assumptions:
- Fill probability decreases with order size relative to volume.
- High-volatility environments have lower fill rates for limit orders.
- The partial fill distribution is approximately Beta-distributed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PartialFillConfig:
    base_fill_probability: float = 0.95
    min_fill_ratio: float = 0.3
    vol_penalty_threshold: float = 0.03
    vol_penalty_multiplier: float = 2.0
    size_penalty_threshold: float = 0.05
    random_seed: int | None = 42


class PartialFillModel:
    """
    Determine fill quantity for a child order.

    Uses a probabilistic model where fill probability depends on:
    - Order size relative to daily volume (larger = lower)
    - Current volatility (higher = lower for limit orders)
    - Base fill probability (configurable)
    """

    def __init__(self, config: PartialFillConfig | None = None) -> None:
        self._config = config or PartialFillConfig()
        self._rng = np.random.default_rng(self._config.random_seed)

    def compute(
        self,
        order_quantity: float,
        daily_volume: float,
        volatility: float = 0.02,
    ) -> tuple[float, bool]:
        """
        Returns (fill_quantity, is_partial).

        Never returns zero unless the order is truly impossible to fill.
        """
        cfg = self._config

        participation = order_quantity / max(daily_volume, 1.0)
        size_penalty = 0.0
        if participation > cfg.size_penalty_threshold:
            size_penalty = min(
                0.3,
                (participation - cfg.size_penalty_threshold) * 5.0,
            )

        vol_penalty = 0.0
        if volatility > cfg.vol_penalty_threshold:
            excess = volatility - cfg.vol_penalty_threshold
            vol_penalty = min(0.2, excess * cfg.vol_penalty_multiplier)

        fill_prob = cfg.base_fill_probability - size_penalty - vol_penalty
        fill_prob = max(0.05, min(1.0, fill_prob))

        if self._rng.random() > fill_prob:
            fill_ratio = self._rng.uniform(cfg.min_fill_ratio, 0.95)
            fill_qty = order_quantity * fill_ratio
            return fill_qty, True

        return order_quantity, False
