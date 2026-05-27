"""
Position sizing — converts alpha signals into position sizes.

Position sizing is where alpha conviction meets portfolio risk constraints.
No position should be sized without considering:
- alpha confidence
- volatility of the instrument
- overall portfolio risk budget
- leverage limits
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


class PositionSizer(ABC):
    @abstractmethod
    def size(
        self,
        alpha_score: float,
        confidence: float,
        price: float,
        volatility: float,
        portfolio_value: float,
        current_position: float,
    ) -> float:
        """Return target position size in shares/contracts."""


@dataclass(frozen=True)
class VolatilityTargetSizer(PositionSizer):
    """
    Size positions to target a specific portfolio volatility contribution.

    target_position_vol * portfolio_value = position_size * price * instrument_vol

    Alpha score and confidence scale the target proportionally.
    """

    target_volatility: float = 0.15
    max_weight: float = 0.20

    def size(
        self,
        alpha_score: float,
        confidence: float,
        price: float,
        volatility: float,
        portfolio_value: float,
        current_position: float,
    ) -> float:
        if portfolio_value <= 0 or price <= 0 or volatility <= 0:
            return 0.0

        vol_target_notional = self.target_volatility * portfolio_value * abs(alpha_score) * confidence
        position_notional = vol_target_notional / max(volatility, 0.01)

        max_notional = self.max_weight * portfolio_value
        position_notional = min(position_notional, max_notional)

        direction = np.sign(alpha_score)
        target_shares = direction * position_notional / price

        return float(target_shares)


@dataclass(frozen=True)
class EqualWeightSizer(PositionSizer):
    """
    Equal-weight position sizing scaled by alpha confidence.

    Useful as a baseline to separate alpha quality from sizing skill.
    """

    base_weight: float = 0.05

    def size(
        self,
        alpha_score: float,
        confidence: float,
        price: float,
        volatility: float,
        portfolio_value: float,
        current_position: float,
    ) -> float:
        if portfolio_value <= 0 or price <= 0:
            return 0.0

        notional = self.base_weight * portfolio_value * confidence
        direction = np.sign(alpha_score)
        return float(direction * notional / price)


@dataclass(frozen=True)
class KellySizer(PositionSizer):
    """
    Half-Kelly sizing for conservative edge exploitation.

    Full Kelly is too aggressive for noisy alpha estimates.
    Half-Kelly is standard institutional practice.
    """

    kelly_fraction: float = 0.5
    max_weight: float = 0.15

    def size(
        self,
        alpha_score: float,
        confidence: float,
        price: float,
        volatility: float,
        portfolio_value: float,
        current_position: float,
    ) -> float:
        if portfolio_value <= 0 or price <= 0 or volatility <= 0:
            return 0.0

        edge = abs(alpha_score) * confidence
        odds = 1.0 / max(volatility, 0.01)
        kelly_weight = self.kelly_fraction * (edge * odds - (1 - edge)) / max(odds, 0.01)
        kelly_weight = max(0.0, min(kelly_weight, self.max_weight))

        notional = kelly_weight * portfolio_value
        direction = np.sign(alpha_score)
        return float(direction * notional / price)
