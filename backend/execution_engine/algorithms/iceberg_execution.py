"""
Iceberg execution algorithm.

Displays only a small "visible" portion of the full order to the market,
replenishing from the hidden reserve as fills occur. Minimizes information
leakage about the true order size.

Statistical assumptions:
- Showing full order size attracts adverse selection from informed traders.
- Small displayed quantities attract less front-running pressure.
- The hidden-to-visible ratio controls the tradeoff between speed and stealth.

Known limitations:
- Sophisticated market participants can detect iceberg patterns from
  repeated same-size replenishments.
- Randomizing displayed size helps but does not eliminate detectability.
- Slower execution than aggressive algorithms — not suitable for urgent orders.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from execution_engine.execution_base import (
    ChildOrder,
    ExecutionAlgorithm,
    OrderStatus,
    OrderType,
    ParentOrder,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IcebergConfig:
    visible_fraction: float = 0.1
    min_visible_quantity: float = 10.0
    max_visible_quantity: float = 1000.0
    randomize_size: bool = True
    size_jitter_fraction: float = 0.3
    replenish_delay_seconds: float = 5.0
    use_limit_orders: bool = True
    limit_offset_bps: float = 2.0


@dataclass(frozen=True)
class IcebergSchedule:
    initial_slice: ChildOrder
    visible_quantity: float
    hidden_quantity: float
    total_quantity: float
    estimated_n_replenishments: int
    warnings: list[str] = field(default_factory=list)


class IcebergAlgorithm:
    """
    Generate iceberg execution plan.

    Creates an initial visible child order and provides a replenishment
    protocol for generating subsequent slices as fills occur.
    """

    def __init__(self, config: IcebergConfig | None = None) -> None:
        self._config = config or IcebergConfig()
        self._rng = np.random.default_rng(42)

    def generate_initial(
        self,
        parent: ParentOrder,
        current_price: float,
        start_time: pd.Timestamp | None = None,
    ) -> IcebergSchedule:
        cfg = self._config
        warnings: list[str] = []

        visible = parent.total_quantity * cfg.visible_fraction
        visible = max(cfg.min_visible_quantity, min(cfg.max_visible_quantity, visible))

        if cfg.randomize_size:
            jitter = self._rng.uniform(
                1.0 - cfg.size_jitter_fraction,
                1.0 + cfg.size_jitter_fraction,
            )
            visible *= jitter
            visible = max(cfg.min_visible_quantity, visible)

        visible = min(visible, parent.total_quantity)
        hidden = parent.total_quantity - visible

        if cfg.use_limit_orders and current_price > 0:
            offset = current_price * cfg.limit_offset_bps / 10_000
            if parent.side.value == "BUY":
                limit_price = current_price + offset
            else:
                limit_price = current_price - offset
            order_type = OrderType.LIMIT
        else:
            limit_price = None
            order_type = OrderType.MARKET

        t_start = start_time or pd.Timestamp.now(tz="UTC")

        child = ChildOrder(
            parent_id=parent.order_id,
            symbol=parent.symbol,
            side=parent.side,
            order_type=order_type,
            quantity=visible,
            limit_price=limit_price,
            scheduled_time=t_start,
            slice_index=0,
            total_slices=max(1, int(parent.total_quantity / visible)),
            status=OrderStatus.PENDING,
            metadata={
                "algorithm": ExecutionAlgorithm.ICEBERG.value,
                "visible_fraction": visible / parent.total_quantity,
                "is_initial": True,
            },
        )

        n_replenish = max(0, int(np.ceil(hidden / visible)))

        if parent.total_quantity * cfg.visible_fraction < cfg.min_visible_quantity:
            warnings.append(
                "Visible fraction produces quantity below minimum. "
                "Order may be detectable as iceberg."
            )

        return IcebergSchedule(
            initial_slice=child,
            visible_quantity=visible,
            hidden_quantity=hidden,
            total_quantity=parent.total_quantity,
            estimated_n_replenishments=n_replenish,
            warnings=warnings,
        )

    def generate_replenishment(
        self,
        parent: ParentOrder,
        filled_so_far: float,
        current_price: float,
        timestamp: pd.Timestamp,
        slice_index: int,
    ) -> ChildOrder | None:
        """Generate the next iceberg replenishment slice."""
        cfg = self._config

        remaining = parent.total_quantity - filled_so_far
        if remaining < cfg.min_visible_quantity:
            return None

        visible = parent.total_quantity * cfg.visible_fraction
        visible = max(cfg.min_visible_quantity, min(cfg.max_visible_quantity, visible))

        if cfg.randomize_size:
            jitter = self._rng.uniform(
                1.0 - cfg.size_jitter_fraction,
                1.0 + cfg.size_jitter_fraction,
            )
            visible *= jitter
            visible = max(cfg.min_visible_quantity, visible)

        visible = min(visible, remaining)

        if cfg.use_limit_orders and current_price > 0:
            offset = current_price * cfg.limit_offset_bps / 10_000
            if parent.side.value == "BUY":
                limit_price = current_price + offset
            else:
                limit_price = current_price - offset
            order_type = OrderType.LIMIT
        else:
            limit_price = None
            order_type = OrderType.MARKET

        scheduled = timestamp + pd.Timedelta(seconds=cfg.replenish_delay_seconds)

        return ChildOrder(
            parent_id=parent.order_id,
            symbol=parent.symbol,
            side=parent.side,
            order_type=order_type,
            quantity=visible,
            limit_price=limit_price,
            scheduled_time=scheduled,
            slice_index=slice_index,
            total_slices=max(1, int(parent.total_quantity / visible)),
            status=OrderStatus.PENDING,
            metadata={
                "algorithm": ExecutionAlgorithm.ICEBERG.value,
                "visible_fraction": visible / parent.total_quantity,
                "is_replenishment": True,
            },
        )
