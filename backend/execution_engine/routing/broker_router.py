"""
Broker router — selects execution destination based on order characteristics.

Routes orders to the appropriate execution venue based on:
- Order size and urgency
- Asset type and liquidity
- Cost optimization
- Venue capabilities

This module is a routing framework ready for live broker integration.
Currently operates in simulation mode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique

from execution_engine.execution_base import ParentOrder, ExecutionUrgency

logger = logging.getLogger(__name__)


@unique
class VenueType(Enum):
    PRIMARY_EXCHANGE = "primary_exchange"
    DARK_POOL = "dark_pool"
    ECN = "ecn"
    INTERNAL_CROSS = "internal_cross"
    SIMULATED = "simulated"


@dataclass(frozen=True)
class VenueProfile:
    venue_id: str
    venue_type: VenueType
    supported_symbols: set[str] = field(default_factory=set)
    avg_latency_ms: float = 50.0
    fee_bps: float = 1.0
    max_order_size: float = float("inf")
    min_order_size: float = 1.0
    supports_limit: bool = True
    supports_iceberg: bool = False
    dark_pool: bool = False
    priority: int = 0


@dataclass(frozen=True)
class RoutingDecision:
    venue_id: str
    venue_type: VenueType
    reason: str
    estimated_cost_bps: float
    warnings: list[str] = field(default_factory=list)


class BrokerRouter:
    """
    Route orders to optimal execution venues.

    Scoring considers cost, latency, and venue suitability for the
    specific order characteristics.
    """

    def __init__(
        self,
        venues: list[VenueProfile] | None = None,
    ) -> None:
        if venues is None:
            venues = [
                VenueProfile(
                    venue_id="sim_primary",
                    venue_type=VenueType.SIMULATED,
                    avg_latency_ms=50.0,
                    fee_bps=1.0,
                ),
            ]
        self._venues = {v.venue_id: v for v in venues}

    def route(self, order: ParentOrder) -> RoutingDecision:
        """Select the best venue for a parent order."""
        warnings: list[str] = []

        eligible = self._filter_eligible(order)
        if not eligible:
            warnings.append("No eligible venues, using default simulated")
            return RoutingDecision(
                venue_id="sim_primary",
                venue_type=VenueType.SIMULATED,
                reason="no eligible venues",
                estimated_cost_bps=5.0,
                warnings=warnings,
            )

        scored = []
        for venue in eligible:
            score = self._score_venue(venue, order)
            scored.append((score, venue))

        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]

        return RoutingDecision(
            venue_id=best.venue_id,
            venue_type=best.venue_type,
            reason=f"best score among {len(eligible)} eligible venues",
            estimated_cost_bps=best.fee_bps,
            warnings=warnings,
        )

    def _filter_eligible(self, order: ParentOrder) -> list[VenueProfile]:
        eligible = []
        for venue in self._venues.values():
            if venue.supported_symbols and order.symbol not in venue.supported_symbols:
                continue
            if order.total_quantity > venue.max_order_size:
                continue
            if order.total_quantity < venue.min_order_size:
                continue
            eligible.append(venue)
        return eligible

    @staticmethod
    def _score_venue(venue: VenueProfile, order: ParentOrder) -> float:
        """
        Score a venue for an order. Higher is better.
        """
        score = 100.0

        score -= venue.fee_bps * 10
        score -= venue.avg_latency_ms * 0.1

        if order.urgency == ExecutionUrgency.IMMEDIATE:
            score -= venue.avg_latency_ms * 0.5
        elif order.urgency == ExecutionUrgency.LOW:
            score -= venue.fee_bps * 20

        if venue.dark_pool and order.total_quantity > 10_000:
            score += 10

        score += venue.priority * 5

        return score
