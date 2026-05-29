"""
Execution gateway — unified interface for order submission and management.

Acts as the single entry point for all execution requests, routing through
validation, routing, and scheduling layers.

Designed for future extension to support:
- FIX protocol integration
- REST API broker connections
- WebSocket streaming venues
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from execution_engine.execution_base import (
    ExecutionResult,
    OrderStatus,
    ParentOrder,
)
from execution_engine.routing.broker_router import BrokerRouter, RoutingDecision

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GatewayConfig:
    max_order_value: float = 10_000_000.0
    max_orders_per_minute: int = 100
    reject_nan_quantities: bool = True
    reject_negative_prices: bool = True
    require_symbol: bool = True


@dataclass(frozen=True)
class SubmissionResult:
    accepted: bool
    order_id: str
    routing: RoutingDecision | None = None
    rejection_reason: str = ""
    warnings: list[str] = field(default_factory=list)


class ExecutionGateway:
    """
    Unified execution gateway with validation and routing.

    All orders pass through validation before being routed and scheduled.
    """

    def __init__(
        self,
        config: GatewayConfig | None = None,
        router: BrokerRouter | None = None,
    ) -> None:
        self._config = config or GatewayConfig()
        self._router = router or BrokerRouter()
        self._submission_count = 0
        self._last_minute: pd.Timestamp | None = None

    def submit(
        self,
        order: ParentOrder,
        market_price: float | None = None,
    ) -> SubmissionResult:
        """
        Validate and route an order for execution.
        """
        cfg = self._config
        warnings: list[str] = []

        rejection = self._validate(order, market_price)
        if rejection:
            return SubmissionResult(
                accepted=False,
                order_id=order.order_id,
                rejection_reason=rejection,
            )

        routing = self._router.route(order)
        warnings.extend(routing.warnings)

        self._submission_count += 1

        return SubmissionResult(
            accepted=True,
            order_id=order.order_id,
            routing=routing,
            warnings=warnings,
        )

    def _validate(
        self,
        order: ParentOrder,
        market_price: float | None,
    ) -> str | None:
        """Return rejection reason, or None if valid."""
        cfg = self._config

        if cfg.require_symbol and not order.symbol:
            return "Missing symbol"

        if cfg.reject_nan_quantities and (
            not np.isfinite(order.total_quantity) or order.total_quantity <= 0
        ):
            return f"Invalid quantity: {order.total_quantity}"

        if cfg.reject_negative_prices and order.limit_price is not None:
            if not np.isfinite(order.limit_price) or order.limit_price <= 0:
                return f"Invalid limit price: {order.limit_price}"

        if market_price and market_price > 0:
            notional = order.total_quantity * market_price
            if notional > cfg.max_order_value:
                return (
                    f"Order value {notional:.0f} exceeds max {cfg.max_order_value:.0f}"
                )

        return None
