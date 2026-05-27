"""
Spread models — bid-ask spread simulation.

Spread is NOT fixed. It widens during volatility, narrows in calm markets,
and varies by instrument liquidity. Crossing the spread is a real cost
that many retail backtests ignore entirely.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class SpreadModel(ABC):
    @abstractmethod
    def estimate(
        self,
        price: float,
        volatility: float,
        volume: float,
        rng: np.random.Generator,
    ) -> float:
        """Return half-spread in price units (cost per side of crossing)."""


@dataclass(frozen=True)
class VolatilityAdjustedSpread(SpreadModel):
    """
    Spread widens with volatility and narrows with volume.

    half_spread = max(min_bps, base_bps * (1 + vol_scale * vol) / volume_factor) * price
    """

    base_bps: float = 3.0
    min_bps: float = 1.0
    vol_scale: float = 2.0
    volume_dampening: float = 0.1

    def estimate(
        self,
        price: float,
        volatility: float,
        volume: float,
        rng: np.random.Generator,
    ) -> float:
        vol_widening = 1.0 + self.vol_scale * volatility
        volume_factor = 1.0 / (1.0 + self.volume_dampening * np.log1p(volume))
        spread_bps = max(self.min_bps, self.base_bps * vol_widening * volume_factor)
        noise = rng.uniform(0.8, 1.2)
        return spread_bps * 1e-4 * price * noise


@dataclass(frozen=True)
class FixedSpread(SpreadModel):
    """Fixed half-spread for instruments with known tight spreads."""

    half_spread_bps: float = 2.0

    def estimate(
        self,
        price: float,
        volatility: float,
        volume: float,
        rng: np.random.Generator,
    ) -> float:
        return self.half_spread_bps * 1e-4 * price


@dataclass(frozen=True)
class QuotedSpread(SpreadModel):
    """Use actual bid/ask data when available (passthrough)."""

    def estimate(
        self,
        price: float,
        volatility: float,
        volume: float,
        rng: np.random.Generator,
    ) -> float:
        raise NotImplementedError(
            "QuotedSpread requires bid/ask prices — use estimate_from_quotes instead"
        )

    def estimate_from_quotes(self, bid: float, ask: float) -> float:
        return (ask - bid) / 2.0
