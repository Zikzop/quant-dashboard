"""
Liquidity model — estimates available liquidity for execution.

Models the relationship between order size, participation rate, and
available market liquidity. Large orders relative to market volume
face liquidity constraints that limit fill sizes.

Statistical assumptions:
- Available liquidity decays with order size (diminishing marginal availability).
- Liquidity is lower during high-volatility periods (liquidity withdrawal).
- Participation rates above a threshold cause liquidity deterioration.

Known limitations:
- Intraday liquidity variation is not modeled (would need order book data).
- Cross-asset liquidity correlations (flight-to-quality) are not captured.
- Liquidity is modeled as a scalar, not a curve (no order book depth).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiquidityConfig:
    max_participation_rate: float = 0.10
    liquidity_decay_exponent: float = 1.5
    vol_liquidity_penalty: float = 0.3
    vol_threshold: float = 0.03
    min_available_fraction: float = 0.01


class LiquidityModel:
    """
    Estimate available liquidity for an order.

    Returns the maximum quantity that can be filled given current
    market conditions and participation constraints.
    """

    def __init__(self, config: LiquidityConfig | None = None) -> None:
        self._config = config or LiquidityConfig()

    def available_liquidity(
        self,
        order_quantity: float,
        daily_volume: float,
        participation_rate: float = 0.05,
        volatility: float = 0.02,
    ) -> float:
        """
        Compute available fill quantity given liquidity constraints.

        Parameters
        ----------
        order_quantity : desired fill size
        daily_volume : estimated daily volume
        participation_rate : target participation rate
        volatility : current asset volatility (daily)
        """
        cfg = self._config

        if daily_volume <= 0:
            return order_quantity * cfg.min_available_fraction

        effective_rate = min(participation_rate, cfg.max_participation_rate)

        base_available = daily_volume * effective_rate

        if volatility > cfg.vol_threshold:
            vol_penalty = 1.0 - cfg.vol_liquidity_penalty * (
                (volatility - cfg.vol_threshold) / cfg.vol_threshold
            )
            vol_penalty = max(0.2, vol_penalty)
            base_available *= vol_penalty

        if order_quantity > base_available:
            ratio = order_quantity / base_available
            decay = ratio ** (-cfg.liquidity_decay_exponent + 1)
            available = base_available * min(1.0, decay)
        else:
            available = order_quantity

        available = max(available, order_quantity * cfg.min_available_fraction)
        available = min(available, order_quantity)

        return float(available)

    def estimate_impact_from_size(
        self,
        order_quantity: float,
        daily_volume: float,
    ) -> float:
        """
        Quick estimate of market impact in basis points from order size.

        Uses the square-root model: impact ~ 10000 * σ * sqrt(Q/V).
        Without volatility, uses a conservative proxy.
        """
        if daily_volume <= 0:
            return 100.0
        participation = order_quantity / daily_volume
        impact_bps = 10.0 * np.sqrt(participation) * 10_000
        return float(min(impact_bps, 500.0))
