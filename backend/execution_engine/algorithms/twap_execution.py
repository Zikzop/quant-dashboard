"""
Time-Weighted Average Price (TWAP) execution algorithm.

Splits a parent order into equal-sized time slices over the execution window.
Each slice generates a child order submitted at evenly-spaced intervals.

TWAP minimizes timing risk by distributing execution uniformly across time,
but does not adapt to volume patterns.

Statistical assumptions:
- Price path within the execution window is approximately a random walk.
- Market impact per slice is independent (weak assumption for large orders).
- Time slices are independent opportunities — no serial correlation in fills.

Known limitations:
- Ignores volume profile: trades equally in low- and high-volume periods.
- Predictable execution pattern can be front-run by informed traders.
- Fixed schedule cannot adapt to adverse price movements within the window.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from execution_engine.execution_base import (
    ChildOrder,
    ExecutionAlgorithm,
    OrderSide,
    OrderStatus,
    OrderType,
    ParentOrder,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TWAPConfig:
    min_slices: int = 5
    max_slices: int = 100
    default_duration_minutes: int = 60
    min_slice_quantity: float = 1.0
    randomize_timing: bool = True
    timing_jitter_fraction: float = 0.1


@dataclass(frozen=True)
class TWAPSchedule:
    slices: list[ChildOrder]
    total_quantity: float
    n_slices: int
    slice_interval_seconds: float
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    warnings: list[str] = field(default_factory=list)


class TWAPAlgorithm:
    """
    Generate TWAP execution schedule from a parent order.

    Produces a list of child orders with evenly-spaced scheduled times
    and equal quantities (±1 unit for remainder distribution).
    """

    def __init__(self, config: TWAPConfig | None = None) -> None:
        self._config = config or TWAPConfig()

    def generate_schedule(
        self,
        parent: ParentOrder,
        start_time: pd.Timestamp | None = None,
        end_time: pd.Timestamp | None = None,
        n_slices: int | None = None,
    ) -> TWAPSchedule:
        cfg = self._config
        warnings: list[str] = []

        t_start = start_time or parent.start_time or pd.Timestamp.now(tz="UTC")
        if end_time:
            t_end = end_time
        elif parent.end_time:
            t_end = parent.end_time
        else:
            t_end = t_start + pd.Timedelta(minutes=cfg.default_duration_minutes)

        duration = (t_end - t_start).total_seconds()
        if duration <= 0:
            warnings.append("Invalid duration, using default")
            t_end = t_start + pd.Timedelta(minutes=cfg.default_duration_minutes)
            duration = cfg.default_duration_minutes * 60

        if n_slices is None:
            n_slices = max(
                cfg.min_slices,
                min(cfg.max_slices, int(parent.total_quantity / cfg.min_slice_quantity)),
            )

        n_slices = max(cfg.min_slices, min(cfg.max_slices, n_slices))

        base_qty = parent.total_quantity / n_slices
        if base_qty < cfg.min_slice_quantity:
            n_slices = max(1, int(parent.total_quantity / cfg.min_slice_quantity))
            base_qty = parent.total_quantity / n_slices
            warnings.append(f"Reduced slices to {n_slices} for minimum slice size")

        slice_interval = duration / n_slices

        quantities = [base_qty] * n_slices
        remainder = parent.total_quantity - sum(quantities)
        for i in range(int(round(abs(remainder) / max(1e-10, base_qty) * n_slices))):
            if i < n_slices:
                quantities[i] += remainder / n_slices

        rng = np.random.default_rng(hash(parent.order_id) % (2**31))

        children = []
        for i in range(n_slices):
            scheduled = t_start + pd.Timedelta(seconds=slice_interval * (i + 0.5))

            if cfg.randomize_timing:
                jitter = rng.uniform(
                    -cfg.timing_jitter_fraction * slice_interval,
                    cfg.timing_jitter_fraction * slice_interval,
                )
                scheduled += pd.Timedelta(seconds=jitter)
                scheduled = max(scheduled, t_start)
                scheduled = min(scheduled, t_end)

            child = ChildOrder(
                parent_id=parent.order_id,
                symbol=parent.symbol,
                side=parent.side,
                order_type=OrderType.MARKET,
                quantity=quantities[i],
                scheduled_time=scheduled,
                slice_index=i,
                total_slices=n_slices,
                status=OrderStatus.PENDING,
                metadata={
                    "algorithm": ExecutionAlgorithm.TWAP.value,
                    "slice_fraction": quantities[i] / parent.total_quantity,
                },
            )
            children.append(child)

        children.sort(key=lambda c: c.scheduled_time)

        return TWAPSchedule(
            slices=children,
            total_quantity=parent.total_quantity,
            n_slices=n_slices,
            slice_interval_seconds=slice_interval,
            start_time=t_start,
            end_time=t_end,
            warnings=warnings,
        )
