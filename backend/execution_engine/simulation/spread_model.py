"""
Bid-ask spread model — estimates execution spread costs.

The bid-ask spread is the most basic and unavoidable transaction cost.
This model estimates the effective spread based on market conditions.

Statistical assumptions:
- Spreads widen with volatility (market maker uncertainty).
- Spreads narrow with volume (more competition among liquidity providers).
- Large orders face wider effective spreads due to walking the book.
- Spread costs are always incurred — there is no free execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SpreadConfig:
    base_spread_bps: float = 3.0
    min_spread_bps: float = 0.5
    max_spread_bps: float = 30.0
    vol_sensitivity: float = 2.0
    volume_sensitivity: float = -0.3
    size_walk_coefficient: float = 0.5
    random_seed: int | None = 42


class SpreadModel:
    """
    Estimate effective bid-ask spread for execution costing.
    """

    def __init__(self, config: SpreadConfig | None = None) -> None:
        self._config = config or SpreadConfig()
        self._rng = np.random.default_rng(self._config.random_seed)

    def compute(
        self,
        volatility: float = 0.02,
        daily_volume: float = 1_000_000.0,
        order_size: float = 100.0,
    ) -> float:
        """
        Returns half-spread in basis points (one-sided cost).

        The full round-trip cost is 2x this value.
        """
        cfg = self._config

        vol_adjustment = 1.0 + cfg.vol_sensitivity * max(0, volatility - 0.01)

        if daily_volume > 0:
            log_vol = np.log10(max(daily_volume, 1.0))
            volume_adjustment = 1.0 + cfg.volume_sensitivity * (log_vol - 5.0) / 5.0
            volume_adjustment = max(0.3, volume_adjustment)
        else:
            volume_adjustment = 2.0

        if daily_volume > 0 and order_size > 0:
            participation = order_size / daily_volume
            book_walk = cfg.size_walk_coefficient * np.sqrt(participation) * 10_000
        else:
            book_walk = 0.0

        noise = self._rng.uniform(0.9, 1.1)

        spread = (
            cfg.base_spread_bps * vol_adjustment * volume_adjustment + book_walk
        ) * noise

        return float(np.clip(spread / 2.0, cfg.min_spread_bps / 2, cfg.max_spread_bps / 2))
