"""
Event definitions for institutional backtesting.

Strict separation: MarketEvent -> SignalEvent -> OrderEvent -> FillEvent
                   -> PortfolioUpdateEvent -> RiskUpdateEvent

No shortcuts. No collapsing signal+fill into one step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any
from uuid import uuid4

import pandas as pd

from backtesting.event_engine.event_types import EventType


@unique
class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


@unique
class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


@unique
class FillStatus(Enum):
    FILLED = "FILLED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class Event:
    """Base event with timestamp and unique ID for audit trail."""

    event_type: EventType
    timestamp: pd.Timestamp
    event_id: str = field(default_factory=lambda: uuid4().hex[:12])

    def __lt__(self, other: Event) -> bool:
        if self.timestamp == other.timestamp:
            return self.event_type < other.event_type
        return self.timestamp < other.timestamp


@dataclass(frozen=True)
class MarketEvent(Event):
    """
    New market data bar. This is the only source of price truth in the simulation.

    symbol : str
        Instrument identifier.
    open / high / low / close / volume : float
        OHLCV bar data (already finalized — no partial bars).
    bid / ask : float | None
        If available, used for realistic spread modeling.
    """

    event_type: EventType = field(default=EventType.MARKET, init=False)
    symbol: str = ""
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    bid: float | None = None
    ask: float | None = None


@dataclass(frozen=True)
class SignalEvent(Event):
    """
    Alpha signal — probabilistic conviction, not a trade instruction.

    alpha_score and confidence come from AlphaOutput in the alpha engine.
    The portfolio engine decides whether and how much to trade.
    """

    event_type: EventType = field(default=EventType.SIGNAL, init=False)
    symbol: str = ""
    alpha_name: str = ""
    alpha_score: float = 0.0
    confidence: float = 0.0
    regime_context: dict[str, Any] = field(default_factory=dict)
    target_weight: float | None = None


@dataclass(frozen=True)
class OrderEvent(Event):
    """
    Order submitted to the execution simulator.

    An order is NOT a fill. The fill simulator decides actual execution.
    """

    event_type: EventType = field(default=EventType.ORDER, init=False)
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: float = 0.0
    limit_price: float | None = None
    signal_event_id: str = ""


@dataclass(frozen=True)
class FillEvent(Event):
    """
    Execution report from the fill simulator.

    fill_price != order price due to slippage, spread, and market impact.
    quantity_filled <= quantity_ordered due to partial fills.
    """

    event_type: EventType = field(default=EventType.FILL, init=False)
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity_ordered: float = 0.0
    quantity_filled: float = 0.0
    fill_price: float = 0.0
    slippage: float = 0.0
    spread_cost: float = 0.0
    market_impact: float = 0.0
    commission: float = 0.0
    total_cost: float = 0.0
    fill_status: FillStatus = FillStatus.FILLED
    order_event_id: str = ""
    latency_ms: float = 0.0


@dataclass(frozen=True)
class PortfolioUpdateEvent(Event):
    """Portfolio state change after a fill is processed."""

    event_type: EventType = field(default=EventType.PORTFOLIO_UPDATE, init=False)
    symbol: str = ""
    new_position: float = 0.0
    new_weight: float = 0.0
    portfolio_value: float = 0.0
    cash: float = 0.0
    fill_event_id: str = ""


@dataclass(frozen=True)
class RiskUpdateEvent(Event):
    """Post-trade risk snapshot for constraint enforcement."""

    event_type: EventType = field(default=EventType.RISK_UPDATE, init=False)
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    leverage: float = 0.0
    max_position_weight: float = 0.0
    portfolio_volatility: float = 0.0
    drawdown: float = 0.0
    risk_budget_used: float = 0.0
    constraint_violations: tuple[str, ...] = ()
