"""
Leverage constraints — enforce portfolio-level risk limits.

Leverage constraints are hard limits, not soft targets.
When violated, positions must be scaled down before new trades.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backtesting.portfolio.portfolio_state import PortfolioState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LeverageConstraints:
    """Portfolio-level leverage and exposure constraints."""

    max_gross_leverage: float = 1.0
    max_net_exposure_ratio: float = 1.0
    max_position_weight: float = 0.20
    max_sector_weight: float = 0.40
    min_cash_reserve_pct: float = 0.05

    def scale_order(
        self,
        state: PortfolioState,
        symbol: str,
        proposed_quantity: float,
        price: float,
    ) -> float:
        """
        Scale down proposed order quantity to respect constraints.

        Returns adjusted quantity (may be zero if constraints forbid the trade).
        """
        pv = state.portfolio_value
        if pv <= 0:
            return 0.0

        proposed_notional = abs(proposed_quantity * price)
        current_gross = state.gross_exposure
        new_gross = current_gross + proposed_notional
        max_gross = self.max_gross_leverage * pv

        if new_gross > max_gross:
            available = max(0.0, max_gross - current_gross)
            if available <= 0:
                logger.debug("Leverage constraint blocks trade on %s", symbol)
                return 0.0
            scale = available / proposed_notional
            proposed_quantity *= scale

        position_notional = abs(proposed_quantity * price)
        max_pos = self.max_position_weight * pv
        current_pos = state.get_position(symbol)
        existing_notional = abs(current_pos.market_value)

        if existing_notional + position_notional > max_pos:
            available = max(0.0, max_pos - existing_notional)
            if available <= 0:
                return 0.0
            scale = available / position_notional
            proposed_quantity *= scale

        min_cash = self.min_cash_reserve_pct * pv
        trade_cash = abs(proposed_quantity * price)
        if state.cash - trade_cash < min_cash:
            available_cash = max(0.0, state.cash - min_cash)
            if available_cash <= 0:
                return 0.0
            scale = available_cash / trade_cash
            proposed_quantity *= scale

        return proposed_quantity
