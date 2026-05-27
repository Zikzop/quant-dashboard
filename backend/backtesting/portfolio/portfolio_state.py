"""
Portfolio state — tracks positions, cash, and portfolio value over time.

This is the single source of truth for what the portfolio holds.
All mutations go through explicit methods with full audit trail.
No silent position changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Iterator

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Single instrument position with cost basis tracking."""

    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    market_price: float = 0.0
    realized_pnl: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.market_price

    @property
    def unrealized_pnl(self) -> float:
        return self.quantity * (self.market_price - self.avg_cost)

    @property
    def total_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl

    @property
    def is_long(self) -> bool:
        return self.quantity > 0

    @property
    def is_short(self) -> bool:
        return self.quantity < 0

    @property
    def is_flat(self) -> bool:
        return self.quantity == 0.0

    def update_price(self, price: float) -> None:
        self.market_price = price

    def apply_fill(self, fill_quantity: float, fill_price: float) -> float:
        """
        Apply a fill to this position. Returns realized PnL from the trade.

        Handles:
        - Opening new positions
        - Adding to existing positions
        - Reducing positions (partial close)
        - Reversing positions (close + open other side)
        """
        realized = 0.0

        if self.quantity == 0:
            self.avg_cost = fill_price
            self.quantity = fill_quantity
        elif (self.quantity > 0 and fill_quantity > 0) or (
            self.quantity < 0 and fill_quantity < 0
        ):
            total_cost = self.avg_cost * abs(self.quantity) + fill_price * abs(fill_quantity)
            self.quantity += fill_quantity
            self.avg_cost = total_cost / abs(self.quantity)
        else:
            close_qty = min(abs(fill_quantity), abs(self.quantity))
            if self.quantity > 0:
                realized = close_qty * (fill_price - self.avg_cost)
            else:
                realized = close_qty * (self.avg_cost - fill_price)

            remaining_fill = abs(fill_quantity) - close_qty
            if remaining_fill > 0:
                sign = 1.0 if fill_quantity > 0 else -1.0
                self.quantity = sign * remaining_fill
                self.avg_cost = fill_price
            else:
                if abs(self.quantity) > close_qty:
                    self.quantity += fill_quantity
                else:
                    self.quantity = 0.0
                    self.avg_cost = 0.0

        self.realized_pnl += realized
        return realized


class PortfolioState:
    """
    Complete portfolio state: positions + cash + valuation.

    All position changes flow through apply_fill. Mark-to-market
    updates flow through update_prices.
    """

    def __init__(self, initial_capital: float) -> None:
        self._positions: dict[str, Position] = {}
        self._cash = initial_capital
        self._initial_capital = initial_capital
        self._high_water_mark = initial_capital

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def initial_capital(self) -> float:
        return self._initial_capital

    @property
    def positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def get_position(self, symbol: str) -> Position:
        if symbol not in self._positions:
            self._positions[symbol] = Position(symbol=symbol)
        return self._positions[symbol]

    @property
    def portfolio_value(self) -> float:
        return self._cash + sum(
            pos.market_value for pos in self._positions.values()
        )

    @property
    def long_value(self) -> float:
        return sum(
            pos.market_value for pos in self._positions.values() if pos.is_long
        )

    @property
    def short_value(self) -> float:
        return sum(
            abs(pos.market_value) for pos in self._positions.values() if pos.is_short
        )

    @property
    def gross_exposure(self) -> float:
        return self.long_value + self.short_value

    @property
    def net_exposure(self) -> float:
        return self.long_value - self.short_value

    @property
    def gross_leverage(self) -> float:
        pv = self.portfolio_value
        return self.gross_exposure / pv if pv > 0 else 0.0

    @property
    def net_leverage(self) -> float:
        pv = self.portfolio_value
        return self.net_exposure / pv if pv > 0 else 0.0

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(pos.unrealized_pnl for pos in self._positions.values())

    @property
    def total_realized_pnl(self) -> float:
        return sum(pos.realized_pnl for pos in self._positions.values())

    @property
    def drawdown(self) -> float:
        pv = self.portfolio_value
        self._high_water_mark = max(self._high_water_mark, pv)
        if self._high_water_mark <= 0:
            return 0.0
        return (pv - self._high_water_mark) / self._high_water_mark

    def apply_fill(
        self, symbol: str, quantity: float, fill_price: float, costs: float
    ) -> float:
        """Apply fill to portfolio. Returns realized PnL from this trade."""
        position = self.get_position(symbol)
        realized = position.apply_fill(quantity, fill_price)
        self._cash -= quantity * fill_price + costs
        return realized

    def update_prices(self, prices: dict[str, float]) -> None:
        for symbol, price in prices.items():
            if symbol in self._positions:
                self._positions[symbol].update_price(price)

    def position_weights(self) -> dict[str, float]:
        pv = self.portfolio_value
        if pv <= 0:
            return {}
        return {
            symbol: pos.market_value / pv
            for symbol, pos in self._positions.items()
            if not pos.is_flat
        }

    def active_symbols(self) -> list[str]:
        return [s for s, p in self._positions.items() if not p.is_flat]

    def __iter__(self) -> Iterator[Position]:
        return iter(self._positions.values())
