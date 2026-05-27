"""
Slippage model — estimates price slippage from execution.

Slippage is the difference between the expected execution price and the
actual fill price, caused by:
1. Market movement during execution latency
2. Information leakage from the order itself
3. Queue priority effects

Statistical assumptions:
- Slippage is positively correlated with volatility and order size.
- The slippage distribution is right-skewed (large slippages are more likely
  than large improvements).
- Base slippage scales with the square root of participation rate.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from execution_engine.execution_base import OrderSide

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlippageConfig:
    base_slippage_bps: float = 3.0
    volatility_multiplier: float = 1.5
    size_exponent: float = 0.5
    max_slippage_bps: float = 50.0
    asymmetry_factor: float = 0.6
    random_seed: int | None = 42


class SlippageModel:
    """
    Compute expected slippage for an order.

    Slippage is modeled as:
        slippage_bps = base + vol_mult * σ * (Q/V)^exp + noise

    Where noise is drawn from a skewed distribution favoring adverse fills.
    """

    def __init__(self, config: SlippageConfig | None = None) -> None:
        self._config = config or SlippageConfig()
        self._rng = np.random.default_rng(self._config.random_seed)

    def compute(
        self,
        order_size: float,
        daily_volume: float,
        volatility: float = 0.02,
        side: OrderSide = OrderSide.BUY,
    ) -> float:
        """
        Returns slippage in basis points (always non-negative for adverse).
        """
        cfg = self._config

        if daily_volume <= 0:
            return cfg.max_slippage_bps

        participation = order_size / daily_volume
        size_component = (participation ** cfg.size_exponent) * 10_000

        vol_component = volatility * cfg.volatility_multiplier * 10_000

        noise = self._rng.exponential(scale=cfg.base_slippage_bps * 0.3)
        noise *= cfg.asymmetry_factor

        slippage = cfg.base_slippage_bps + size_component + vol_component * participation + noise

        return float(min(max(slippage, 0.0), cfg.max_slippage_bps))
