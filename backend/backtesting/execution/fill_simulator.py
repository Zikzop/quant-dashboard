"""
Fill simulator — converts OrderEvents into FillEvents with realistic execution.

This is where idealized signals meet market reality. Every order goes through:
1. Latency delay
2. Fill probability check
3. Partial fill simulation
4. Price degradation (slippage + spread + market impact)
5. Commission calculation

The result is a FillEvent that reflects what a real execution would look like,
not what the signal wished for.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from backtesting.event_engine.events import (
    FillEvent,
    FillStatus,
    MarketEvent,
    OrderEvent,
    OrderSide,
)
from backtesting.execution.latency_models import LatencyModel, LogNormalLatency
from backtesting.execution.market_impact import MarketImpactModel, SquareRootImpact
from backtesting.execution.slippage_models import SlippageModel, VolatilityScaledSlippage
from backtesting.execution.spread_models import SpreadModel, VolatilityAdjustedSpread
from backtesting.simulation_config import ExecutionConfig

logger = logging.getLogger(__name__)


@dataclass
class MarketSnapshot:
    """Latest market state for a symbol, used by fill simulator."""

    price: float
    bid: float | None
    ask: float | None
    volume: float
    volatility: float
    avg_volume: float


class FillSimulator:
    """
    Simulates realistic order execution.

    Combines slippage, spread, latency, market impact, and partial fill
    models to produce FillEvents from OrderEvents.
    """

    def __init__(
        self,
        config: ExecutionConfig | None = None,
        slippage_model: SlippageModel | None = None,
        spread_model: SpreadModel | None = None,
        latency_model: LatencyModel | None = None,
        impact_model: MarketImpactModel | None = None,
        rng: np.random.Generator | None = None,
    ) -> None:
        cfg = config or ExecutionConfig()
        self._slippage = slippage_model or VolatilityScaledSlippage(
            base_bps=cfg.base_slippage_bps,
            vol_multiplier=cfg.volatility_slippage_multiplier,
        )
        self._spread = spread_model or VolatilityAdjustedSpread(
            base_bps=cfg.base_spread_bps,
            min_bps=cfg.min_spread_bps,
        )
        self._latency = latency_model or LogNormalLatency(
            mean_ms=cfg.latency_mean_ms,
            std_ms=cfg.latency_std_ms,
        )
        self._impact = impact_model or SquareRootImpact(
            coefficient=cfg.market_impact_coefficient,
            exponent=cfg.market_impact_exponent,
        )
        self._rng = rng or np.random.default_rng(42)
        self._fill_probability = cfg.fill_probability
        self._partial_fill_prob = cfg.partial_fill_probability
        self._min_fill_ratio = cfg.min_fill_ratio
        self._fill_count = 0
        self._reject_count = 0

    def simulate_fill(
        self,
        order: OrderEvent,
        snapshot: MarketSnapshot,
    ) -> FillEvent:
        """
        Simulate execution of an order against current market state.

        Returns a FillEvent with realistic price, quantity, and cost fields.
        """
        if self._rng.random() > self._fill_probability:
            self._reject_count += 1
            return FillEvent(
                timestamp=order.timestamp,
                symbol=order.symbol,
                side=order.side,
                quantity_ordered=order.quantity,
                quantity_filled=0.0,
                fill_price=0.0,
                fill_status=FillStatus.REJECTED,
                order_event_id=order.event_id,
            )

        quantity_filled = order.quantity
        fill_status = FillStatus.FILLED

        if self._rng.random() < self._partial_fill_prob:
            fill_ratio = self._rng.uniform(self._min_fill_ratio, 0.99)
            quantity_filled = order.quantity * fill_ratio
            fill_status = FillStatus.PARTIAL

        latency = self._latency.sample_latency_ms(self._rng)

        slippage = self._slippage.estimate(
            price=snapshot.price,
            quantity=quantity_filled,
            volatility=snapshot.volatility,
            avg_volume=snapshot.avg_volume,
            rng=self._rng,
        )

        spread_cost = self._spread.estimate(
            price=snapshot.price,
            volatility=snapshot.volatility,
            volume=snapshot.volume,
            rng=self._rng,
        )

        impact = self._impact.estimate(
            price=snapshot.price,
            quantity=quantity_filled,
            avg_volume=snapshot.avg_volume,
            volatility=snapshot.volatility,
        )

        direction = 1.0 if order.side == OrderSide.BUY else -1.0
        fill_price = snapshot.price + direction * (slippage + spread_cost + impact)

        total_cost = (slippage + spread_cost + impact) * abs(quantity_filled)

        self._fill_count += 1

        return FillEvent(
            timestamp=order.timestamp,
            symbol=order.symbol,
            side=order.side,
            quantity_ordered=order.quantity,
            quantity_filled=quantity_filled,
            fill_price=fill_price,
            slippage=slippage * abs(quantity_filled),
            spread_cost=spread_cost * abs(quantity_filled),
            market_impact=impact * abs(quantity_filled),
            total_cost=total_cost,
            fill_status=fill_status,
            order_event_id=order.event_id,
            latency_ms=latency,
        )

    @property
    def stats(self) -> dict[str, int]:
        return {
            "fills": self._fill_count,
            "rejects": self._reject_count,
            "fill_rate": self._fill_count / max(1, self._fill_count + self._reject_count),
        }
