"""
Commission models — broker and exchange fee structures.

Commission is the most predictable cost component but varies
dramatically by broker, exchange, and instrument type.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class CommissionModel(ABC):
    @abstractmethod
    def calculate(self, quantity: float, price: float) -> float:
        """Return total commission for this trade."""


@dataclass(frozen=True)
class TieredCommission(CommissionModel):
    """
    Per-share commission with min/max bounds.

    Standard US equity commission structure.
    """

    per_share: float = 0.005
    min_per_order: float = 1.0
    max_pct: float = 0.005

    def calculate(self, quantity: float, price: float) -> float:
        notional = abs(quantity) * price
        raw = abs(quantity) * self.per_share
        commission = max(raw, self.min_per_order)
        cap = notional * self.max_pct
        return min(commission, cap)


@dataclass(frozen=True)
class FixedCommission(CommissionModel):
    """Fixed dollar amount per order."""

    per_order: float = 5.0

    def calculate(self, quantity: float, price: float) -> float:
        return self.per_order


@dataclass(frozen=True)
class PercentageCommission(CommissionModel):
    """Percentage of notional value."""

    pct: float = 0.001

    def calculate(self, quantity: float, price: float) -> float:
        return abs(quantity) * price * self.pct


@dataclass(frozen=True)
class ZeroCommission(CommissionModel):
    """Zero commission — intentionally unrealistic, for comparison only."""

    def calculate(self, quantity: float, price: float) -> float:
        return 0.0
