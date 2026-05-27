"""
Slippage cost model — the cost of price movement between signal and fill.

Slippage is the difference between the price when you decide to trade
and the price you actually get. It's larger for:
- volatile instruments
- large orders relative to volume
- fast-moving markets
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SlippageCostModel:
    """
    Volatility-and-participation-scaled slippage cost.

    cost = quantity * price * slippage_rate
    slippage_rate = base_bps * (1 + vol_mult * vol) * (1 + participation ^ exponent)
    """

    base_bps: float = 5.0
    vol_multiplier: float = 1.5
    participation_exponent: float = 0.5

    def estimate(
        self,
        price: float,
        quantity: float,
        volatility: float,
        avg_volume: float,
    ) -> float:
        vol_factor = 1.0 + self.vol_multiplier * volatility
        participation = abs(quantity) / max(avg_volume, 1.0)
        part_factor = 1.0 + participation ** self.participation_exponent
        rate = self.base_bps * 1e-4 * vol_factor * part_factor
        return rate * price * abs(quantity)

    def marginal_cost(
        self,
        price: float,
        quantity: float,
        volatility: float,
        avg_volume: float,
    ) -> float:
        """Cost of the next incremental share — useful for optimal execution."""
        q = abs(quantity)
        cost_at_q = self.estimate(price, q, volatility, avg_volume)
        cost_at_q_plus = self.estimate(price, q + 1, volatility, avg_volume)
        return cost_at_q_plus - cost_at_q
