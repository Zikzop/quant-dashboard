"""
Market impact models — permanent and temporary price impact from trading.

Large orders move prices. This is the single most important cost for
institutional strategies. The square-root model is the standard
starting point (Almgren-Chriss family).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class MarketImpactModel(ABC):
    @abstractmethod
    def estimate(
        self,
        price: float,
        quantity: float,
        avg_volume: float,
        volatility: float,
    ) -> float:
        """Return estimated market impact in price units."""


@dataclass(frozen=True)
class SquareRootImpact(MarketImpactModel):
    """
    Almgren-Chriss square-root market impact model.

    impact = coefficient * volatility * price * sqrt(quantity / avg_volume)

    This is the workhorse model at most systematic funds.
    It captures the empirical observation that impact grows
    sub-linearly with order size.
    """

    coefficient: float = 0.1
    exponent: float = 0.5

    def estimate(
        self,
        price: float,
        quantity: float,
        avg_volume: float,
        volatility: float,
    ) -> float:
        if avg_volume <= 0 or quantity == 0:
            return 0.0
        participation = abs(quantity) / avg_volume
        return (
            self.coefficient
            * volatility
            * price
            * (participation ** self.exponent)
        )


@dataclass(frozen=True)
class LinearImpact(MarketImpactModel):
    """Linear impact — simpler but overestimates for large orders."""

    coefficient: float = 0.05

    def estimate(
        self,
        price: float,
        quantity: float,
        avg_volume: float,
        volatility: float,
    ) -> float:
        if avg_volume <= 0 or quantity == 0:
            return 0.0
        participation = abs(quantity) / avg_volume
        return self.coefficient * volatility * price * participation


@dataclass(frozen=True)
class ZeroImpact(MarketImpactModel):
    """Zero market impact — intentionally unrealistic, for comparison only."""

    def estimate(
        self,
        price: float,
        quantity: float,
        avg_volume: float,
        volatility: float,
    ) -> float:
        return 0.0
