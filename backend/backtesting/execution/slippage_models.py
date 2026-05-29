"""
Slippage models — price deterioration between decision and execution.

No model assumes zero slippage. The base model scales with volatility
because slippage worsens when markets move faster.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class SlippageModel(ABC):
    @abstractmethod
    def estimate(
        self,
        price: float,
        quantity: float,
        volatility: float,
        avg_volume: float,
        rng: np.random.Generator,
    ) -> float:
        """Return slippage in price units (always >= 0)."""


@dataclass(frozen=True)
class VolatilityScaledSlippage(SlippageModel):
    """
    Slippage = base_bps * (1 + vol_multiplier * realized_vol) * price.

    The stochastic component models execution uncertainty:
    actual slippage on any given trade is random around the expected value.
    """

    base_bps: float = 5.0
    vol_multiplier: float = 1.5
    stochastic_scale: float = 0.3

    def estimate(
        self,
        price: float,
        quantity: float,
        volatility: float,
        avg_volume: float,
        rng: np.random.Generator,
    ) -> float:
        base = self.base_bps * 1e-4 * price
        vol_component = base * self.vol_multiplier * volatility
        expected = base + vol_component
        noise = rng.lognormal(0, self.stochastic_scale) if self.stochastic_scale > 0 else 1.0
        return max(0.0, expected * noise)


@dataclass(frozen=True)
class FixedBpsSlippage(SlippageModel):
    """Fixed basis-point slippage (useful as a floor/comparison baseline)."""

    bps: float = 5.0

    def estimate(
        self,
        price: float,
        quantity: float,
        volatility: float,
        avg_volume: float,
        rng: np.random.Generator,
    ) -> float:
        return self.bps * 1e-4 * price


@dataclass(frozen=True)
class VolumeWeightedSlippage(SlippageModel):
    """
    Slippage increases with participation rate (quantity / avg_volume).

    Captures the intuition that large orders relative to typical volume
    face worse execution.
    """

    base_bps: float = 3.0
    participation_exponent: float = 0.6

    def estimate(
        self,
        price: float,
        quantity: float,
        volatility: float,
        avg_volume: float,
        rng: np.random.Generator,
    ) -> float:
        participation = abs(quantity) / max(avg_volume, 1.0)
        base = self.base_bps * 1e-4 * price
        volume_penalty = base * (participation ** self.participation_exponent)
        return max(0.0, base + volume_penalty)
