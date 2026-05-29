"""
Trade ledger — immutable record of every executed trade.

The ledger is the audit trail. Every fill creates a ledger entry.
No trade happens without a record. This supports:
- PnL reconciliation
- Execution quality analysis
- Regulatory compliance simulation
- Cost attribution
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from backtesting.event_engine.events import FillEvent, FillStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LedgerEntry:
    """Single immutable trade record."""

    trade_id: str
    timestamp: pd.Timestamp
    symbol: str
    side: str
    quantity_ordered: float
    quantity_filled: float
    fill_price: float
    slippage: float
    spread_cost: float
    market_impact: float
    commission: float
    total_cost: float
    fill_status: str
    order_id: str
    latency_ms: float


class TradeLedger:
    """Append-only trade ledger."""

    def __init__(self) -> None:
        self._entries: list[LedgerEntry] = []

    def record_fill(self, fill: FillEvent) -> None:
        entry = LedgerEntry(
            trade_id=fill.event_id,
            timestamp=fill.timestamp,
            symbol=fill.symbol,
            side=fill.side.value,
            quantity_ordered=fill.quantity_ordered,
            quantity_filled=fill.quantity_filled,
            fill_price=fill.fill_price,
            slippage=fill.slippage,
            spread_cost=fill.spread_cost,
            market_impact=fill.market_impact,
            commission=fill.commission,
            total_cost=fill.total_cost,
            fill_status=fill.fill_status.value,
            order_id=fill.order_event_id,
            latency_ms=fill.latency_ms,
        )
        self._entries.append(entry)

    def to_dataframe(self) -> pd.DataFrame:
        if not self._entries:
            return pd.DataFrame()
        return pd.DataFrame([
            {
                "trade_id": e.trade_id,
                "timestamp": e.timestamp,
                "symbol": e.symbol,
                "side": e.side,
                "quantity_ordered": e.quantity_ordered,
                "quantity_filled": e.quantity_filled,
                "fill_price": e.fill_price,
                "slippage": e.slippage,
                "spread_cost": e.spread_cost,
                "market_impact": e.market_impact,
                "commission": e.commission,
                "total_cost": e.total_cost,
                "fill_status": e.fill_status,
                "order_id": e.order_id,
                "latency_ms": e.latency_ms,
            }
            for e in self._entries
        ])

    @property
    def n_trades(self) -> int:
        return len(self._entries)

    def trades_for_symbol(self, symbol: str) -> list[LedgerEntry]:
        return [e for e in self._entries if e.symbol == symbol]

    def total_costs(self) -> dict[str, float]:
        if not self._entries:
            return {"slippage": 0, "spread": 0, "impact": 0, "commission": 0, "total": 0}
        return {
            "slippage": sum(e.slippage for e in self._entries),
            "spread": sum(e.spread_cost for e in self._entries),
            "impact": sum(e.market_impact for e in self._entries),
            "commission": sum(e.commission for e in self._entries),
            "total": sum(e.total_cost for e in self._entries),
        }

    def filled_trades(self) -> list[LedgerEntry]:
        return [
            e for e in self._entries
            if e.fill_status in (FillStatus.FILLED.value, FillStatus.PARTIAL.value)
        ]
