"""
Participation-rate execution algorithm.

Maintains a target participation rate (fraction of market volume) throughout
the execution window. Adapts child order sizes based on observed or estimated
volume flow.

Statistical assumptions:
- Volume flow is observable or predictable with reasonable accuracy.
- Maintaining a consistent participation rate distributes impact evenly.
- Market impact scales super-linearly with participation rate — there is a
  threshold beyond which impact becomes excessive.

Known limitations:
- Requires real-time volume data for adaptive mode (simulated here).
- High participation rates (>15%) significantly impact price.
- Volume estimation errors cause deviation from target participation.
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
class ParticipationConfig:
    target_rate: float = 0.05
    min_rate: float = 0.01
    max_rate: float = 0.15
    n_intervals: int = 20
    default_duration_minutes: int = 120
    urgency_rate_multiplier: float = 1.5
    min_slice_quantity: float = 1.0


@dataclass(frozen=True)
class ParticipationSchedule:
    slices: list[ChildOrder]
    target_participation: float
    expected_total_volume: float
    expected_fill_quantity: float
    completion_probability: float
    warnings: list[str] = field(default_factory=list)


class ParticipationAlgorithm:
    """
    Generate participation-rate-based execution schedule.

    Sizes child orders as a fraction of expected volume in each interval.
    """

    def __init__(self, config: ParticipationConfig | None = None) -> None:
        self._config = config or ParticipationConfig()

    def generate_schedule(
        self,
        parent: ParentOrder,
        expected_daily_volume: float,
        start_time: pd.Timestamp | None = None,
        end_time: pd.Timestamp | None = None,
        volume_profile: list[float] | None = None,
    ) -> ParticipationSchedule:
        cfg = self._config
        warnings: list[str] = []

        rate = min(parent.max_participation_rate, cfg.target_rate)
        if parent.urgency.value == "HIGH":
            rate = min(rate * cfg.urgency_rate_multiplier, cfg.max_rate)
        elif parent.urgency.value == "IMMEDIATE":
            rate = cfg.max_rate
        rate = max(cfg.min_rate, min(cfg.max_rate, rate))

        t_start = start_time or parent.start_time or pd.Timestamp.now(tz="UTC")
        if end_time:
            t_end = end_time
        elif parent.end_time:
            t_end = parent.end_time
        else:
            t_end = t_start + pd.Timedelta(minutes=cfg.default_duration_minutes)

        duration = (t_end - t_start).total_seconds()
        interval_duration = duration / cfg.n_intervals
        trading_minutes = duration / 60.0
        trading_day_minutes = 390.0

        fraction_of_day = min(1.0, trading_minutes / trading_day_minutes)
        expected_window_volume = expected_daily_volume * fraction_of_day

        if volume_profile and len(volume_profile) == cfg.n_intervals:
            vol_fracs = volume_profile
        else:
            vol_fracs = [1.0 / cfg.n_intervals] * cfg.n_intervals

        vol_sum = sum(vol_fracs)
        if vol_sum > 0:
            vol_fracs = [v / vol_sum for v in vol_fracs]

        children = []
        cumulative_qty = 0.0
        remaining = parent.total_quantity

        for i in range(cfg.n_intervals):
            interval_volume = expected_window_volume * vol_fracs[i]
            target_qty = interval_volume * rate

            target_qty = min(target_qty, remaining)
            if target_qty < cfg.min_slice_quantity:
                continue

            scheduled = t_start + pd.Timedelta(seconds=interval_duration * (i + 0.5))

            child = ChildOrder(
                parent_id=parent.order_id,
                symbol=parent.symbol,
                side=parent.side,
                order_type=OrderType.MARKET,
                quantity=target_qty,
                scheduled_time=scheduled,
                slice_index=i,
                total_slices=cfg.n_intervals,
                status=OrderStatus.PENDING,
                metadata={
                    "algorithm": ExecutionAlgorithm.PARTICIPATION.value,
                    "target_participation": rate,
                    "interval_volume": interval_volume,
                },
            )
            children.append(child)
            cumulative_qty += target_qty
            remaining -= target_qty

        expected_fill = min(cumulative_qty, parent.total_quantity)
        completion_prob = expected_fill / parent.total_quantity if parent.total_quantity > 0 else 0.0

        if completion_prob < 0.9:
            warnings.append(
                f"Expected completion only {completion_prob:.1%} at "
                f"{rate:.1%} participation. Consider extending window or raising rate."
            )

        if rate > 0.10:
            warnings.append(
                f"High participation rate ({rate:.1%}). "
                "Expect significant market impact."
            )

        return ParticipationSchedule(
            slices=children,
            target_participation=rate,
            expected_total_volume=expected_window_volume,
            expected_fill_quantity=expected_fill,
            completion_probability=completion_prob,
            warnings=warnings,
        )
