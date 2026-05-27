"""
Spread cost model — the implicit cost of crossing the bid-ask spread.

Every market order pays the spread. Limit orders may avoid it but
face non-fill risk. This module models the expected spread cost
as a function of volatility and liquidity.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SpreadCostModel:
    """
    Volatility-adaptive spread cost estimator.

    During high volatility, market makers widen spreads to compensate
    for adverse selection risk. The cost scales accordingly.
    """

    base_spread_bps: float = 3.0
    vol_multiplier: float = 2.0
    min_spread_bps: float = 1.0

    def estimate(
        self,
        price: float,
        quantity: float,
        volatility: float,
    ) -> float:
        spread_bps = max(
            self.min_spread_bps,
            self.base_spread_bps * (1.0 + self.vol_multiplier * volatility),
        )
        half_spread = spread_bps * 1e-4 * price
        return half_spread * abs(quantity)

    def spread_bps_at_vol(self, volatility: float) -> float:
        """Diagnostic: what spread are we assuming at this volatility level?"""
        return max(
            self.min_spread_bps,
            self.base_spread_bps * (1.0 + self.vol_multiplier * volatility),
        )
