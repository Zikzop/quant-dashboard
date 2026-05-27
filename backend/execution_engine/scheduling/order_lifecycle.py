"""
Order lifecycle management — tracks the full state machine of parent orders.

State transitions:
  PENDING → ACTIVE → {PARTIALLY_FILLED → FILLED | CANCELLED | EXPIRED}
  PENDING → REJECTED

All transitions are validated and logged for audit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from execution_engine.execution_base import (
    ExecutionResult,
    OrderStatus,
    ParentOrder,
)

logger = logging.getLogger(__name__)

_VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.ACTIVE, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.ACTIVE: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.PARTIALLY_FILLED: {
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.EXPIRED,
    },
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.EXPIRED: set(),
}


@dataclass
class LifecycleEvent:
    order_id: str
    from_status: OrderStatus
    to_status: OrderStatus
    timestamp: pd.Timestamp
    reason: str = ""


class OrderLifecycleManager:
    """
    Track and validate order state transitions.

    Maintains a complete audit trail of all state changes for each order.
    """

    def __init__(self) -> None:
        self._orders: dict[str, ExecutionResult] = {}
        self._history: dict[str, list[LifecycleEvent]] = {}

    def register(self, parent: ParentOrder) -> ExecutionResult:
        """Register a new parent order, initializing its lifecycle."""
        if parent.order_id in self._orders:
            raise ValueError(f"Order {parent.order_id} already registered")

        result = ExecutionResult(
            parent_order=parent,
            status=OrderStatus.PENDING,
        )
        self._orders[parent.order_id] = result
        self._history[parent.order_id] = [
            LifecycleEvent(
                order_id=parent.order_id,
                from_status=OrderStatus.PENDING,
                to_status=OrderStatus.PENDING,
                timestamp=parent.created_at,
                reason="registered",
            )
        ]
        return result

    def transition(
        self,
        order_id: str,
        new_status: OrderStatus,
        timestamp: pd.Timestamp,
        reason: str = "",
    ) -> bool:
        """
        Attempt a state transition. Returns True if valid and applied.
        """
        if order_id not in self._orders:
            logger.error("Unknown order %s", order_id)
            return False

        result = self._orders[order_id]
        current = result.status

        if new_status not in _VALID_TRANSITIONS.get(current, set()):
            logger.warning(
                "Invalid transition for %s: %s → %s",
                order_id, current.value, new_status.value,
            )
            return False

        result.status = new_status
        self._history[order_id].append(
            LifecycleEvent(
                order_id=order_id,
                from_status=current,
                to_status=new_status,
                timestamp=timestamp,
                reason=reason,
            )
        )
        return True

    def get_result(self, order_id: str) -> ExecutionResult | None:
        return self._orders.get(order_id)

    def get_history(self, order_id: str) -> list[LifecycleEvent]:
        return self._history.get(order_id, [])

    def active_orders(self) -> list[ExecutionResult]:
        return [
            r for r in self._orders.values()
            if r.status in (OrderStatus.PENDING, OrderStatus.ACTIVE, OrderStatus.PARTIALLY_FILLED)
        ]

    def completed_orders(self) -> list[ExecutionResult]:
        return [
            r for r in self._orders.values()
            if r.status in (OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED)
        ]
