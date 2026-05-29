"""
Regulatory and exchange fee models.

Beyond broker commissions, real trades pay:
- SEC fees (Section 31 transaction fee on sells)
- FINRA TAF (Trading Activity Fee)
- Exchange fees (maker/taker)
- Short borrow costs (for short positions)

These are small individually but add up at institutional scale.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RegulatoryFees:
    """US equity regulatory fee schedule."""

    sec_fee_per_dollar: float = 0.0000278
    finra_taf_per_share: float = 0.000166
    finra_taf_max: float = 8.30
    exchange_fee_per_share: float = 0.003

    def calculate(
        self,
        quantity: float,
        price: float,
        is_sell: bool,
    ) -> float:
        total = 0.0
        notional = abs(quantity) * price

        if is_sell:
            total += notional * self.sec_fee_per_dollar

        taf = abs(quantity) * self.finra_taf_per_share
        total += min(taf, self.finra_taf_max)

        total += abs(quantity) * self.exchange_fee_per_share

        return total


@dataclass(frozen=True)
class BorrowCost:
    """Short borrow cost model."""

    annual_rate_bps: float = 50.0
    hard_to_borrow_multiplier: float = 5.0

    def daily_cost(
        self,
        position_value: float,
        hard_to_borrow: bool = False,
    ) -> float:
        """Daily borrow cost for short positions."""
        if position_value >= 0:
            return 0.0
        rate = self.annual_rate_bps * 1e-4
        if hard_to_borrow:
            rate *= self.hard_to_borrow_multiplier
        return abs(position_value) * rate / 252


@dataclass(frozen=True)
class CompositeCostModel:
    """Aggregates all cost components for a single trade."""

    commission_per_share: float = 0.005
    commission_min: float = 1.0
    spread_bps: float = 3.0
    slippage_bps: float = 5.0
    sec_fee_per_dollar: float = 0.0000278
    exchange_fee_per_share: float = 0.003

    def total_cost(
        self,
        quantity: float,
        price: float,
        volatility: float = 0.0,
        is_sell: bool = False,
    ) -> float:
        notional = abs(quantity) * price

        commission = max(abs(quantity) * self.commission_per_share, self.commission_min)
        spread = notional * self.spread_bps * 1e-4 * (1 + 2 * volatility)
        slippage = notional * self.slippage_bps * 1e-4 * (1 + 1.5 * volatility)
        reg = 0.0
        if is_sell:
            reg += notional * self.sec_fee_per_dollar
        reg += abs(quantity) * self.exchange_fee_per_share

        return commission + spread + slippage + reg
