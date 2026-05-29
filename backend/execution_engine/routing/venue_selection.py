"""
Venue selection — intelligent venue choice based on order characteristics.

Provides a higher-level selection layer that considers:
- Order urgency and size
- Historical venue performance
- Current market conditions
- Cost optimization across multiple venues
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from execution_engine.execution_base import (
    ExecutionAlgorithm,
    ExecutionUrgency,
    ParentOrder,
)
from execution_engine.routing.broker_router import VenueProfile, VenueType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VenueRecommendation:
    primary_venue: str
    fallback_venue: str | None
    recommended_algorithm: ExecutionAlgorithm
    split_across_venues: bool
    estimated_total_cost_bps: float
    reason: str
    warnings: list[str] = field(default_factory=list)


class VenueSelector:
    """
    Select optimal venue and algorithm combination for an order.

    Goes beyond simple routing to recommend the best execution strategy.
    """

    def __init__(
        self,
        venues: list[VenueProfile] | None = None,
    ) -> None:
        self._venues = venues or [
            VenueProfile(
                venue_id="sim_primary",
                venue_type=VenueType.SIMULATED,
            ),
        ]

    def select(
        self,
        order: ParentOrder,
        daily_volume: float = 1_000_000.0,
        volatility: float = 0.02,
    ) -> VenueRecommendation:
        warnings: list[str] = []

        participation = order.total_quantity / max(daily_volume, 1.0)

        if order.urgency == ExecutionUrgency.IMMEDIATE:
            algo = ExecutionAlgorithm.IMMEDIATE
            reason = "Immediate urgency requires aggressive execution"
        elif participation > 0.05:
            algo = ExecutionAlgorithm.VWAP
            reason = f"Large order ({participation:.1%} of ADV), VWAP recommended"
            warnings.append("High participation rate — expect significant impact")
        elif participation > 0.01:
            algo = ExecutionAlgorithm.TWAP
            reason = f"Medium order ({participation:.1%} of ADV), TWAP recommended"
        else:
            algo = ExecutionAlgorithm.TWAP
            reason = "Small order, TWAP sufficient"

        if participation > 0.02 and any(
            v.dark_pool for v in self._venues
        ):
            warnings.append("Consider dark pool for reduced information leakage")

        primary = self._venues[0].venue_id
        fallback = self._venues[1].venue_id if len(self._venues) > 1 else None

        split = participation > 0.10 and len(self._venues) > 1

        est_cost = 5.0 + participation * 100 + volatility * 500

        return VenueRecommendation(
            primary_venue=primary,
            fallback_venue=fallback,
            recommended_algorithm=algo,
            split_across_venues=split,
            estimated_total_cost_bps=est_cost,
            reason=reason,
            warnings=warnings,
        )
