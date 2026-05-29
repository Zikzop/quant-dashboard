"""
Execution queue — priority-ordered queue of parent orders awaiting execution.

Orders are prioritized by urgency, then by creation time.
The queue enforces single-symbol serialization: only one parent order
per symbol can be executing at a time.
"""

from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass, field

import pandas as pd

from execution_engine.execution_base import (
    ExecutionUrgency,
    OrderStatus,
    ParentOrder,
)

logger = logging.getLogger(__name__)

_URGENCY_PRIORITY = {
    ExecutionUrgency.IMMEDIATE: 0,
    ExecutionUrgency.HIGH: 1,
    ExecutionUrgency.MEDIUM: 2,
    ExecutionUrgency.LOW: 3,
}


@dataclass(order=True)
class QueueEntry:
    priority: int
    timestamp: pd.Timestamp
    order: ParentOrder = field(compare=False)


class ExecutionQueue:
    """
    Priority queue for parent orders.

    Maintains ordering by urgency then creation time.
    Prevents duplicate submissions and enforces per-symbol limits.
    """

    def __init__(self, max_per_symbol: int = 1) -> None:
        self._heap: list[QueueEntry] = []
        self._active_symbols: dict[str, str] = {}
        self._known_ids: set[str] = set()
        self._max_per_symbol = max_per_symbol

    def submit(self, order: ParentOrder) -> bool:
        """
        Submit a parent order to the queue. Returns True if accepted.
        """
        if order.order_id in self._known_ids:
            logger.warning("Duplicate order ID %s rejected", order.order_id)
            return False

        if order.symbol in self._active_symbols:
            logger.warning(
                "Symbol %s already has active order %s",
                order.symbol,
                self._active_symbols[order.symbol],
            )
            return False

        priority = _URGENCY_PRIORITY.get(order.urgency, 2)
        entry = QueueEntry(
            priority=priority,
            timestamp=order.created_at,
            order=order,
        )
        heapq.heappush(self._heap, entry)
        self._known_ids.add(order.order_id)
        return True

    def next(self) -> ParentOrder | None:
        """Get the next order to execute."""
        while self._heap:
            entry = heapq.heappop(self._heap)
            order = entry.order
            if order.symbol in self._active_symbols:
                heapq.heappush(self._heap, entry)
                return None
            self._active_symbols[order.symbol] = order.order_id
            return order
        return None

    def complete(self, order_id: str, symbol: str) -> None:
        """Mark an order as completed, freeing the symbol slot."""
        if self._active_symbols.get(symbol) == order_id:
            del self._active_symbols[symbol]

    def cancel(self, order_id: str) -> bool:
        """Remove a pending order from the queue."""
        new_heap = []
        found = False
        for entry in self._heap:
            if entry.order.order_id == order_id:
                found = True
            else:
                new_heap.append(entry)
        self._heap = new_heap
        heapq.heapify(self._heap)
        return found

    @property
    def pending_count(self) -> int:
        return len(self._heap)

    @property
    def active_symbols(self) -> dict[str, str]:
        return dict(self._active_symbols)

    def peek(self) -> ParentOrder | None:
        if self._heap:
            return self._heap[0].order
        return None
