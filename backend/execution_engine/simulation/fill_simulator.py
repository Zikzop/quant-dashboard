"""
Fill simulator — generates realistic fill events for child orders.

Coordinates slippage, spread, impact, and partial fill models to produce
fills that reflect real market execution dynamics.

This is the core simulation engine: NO perfect fills, NO zero costs.
Every fill includes explicit friction components.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from execution_engine.execution_base import (
    ChildOrder,
    FillEvent,
    OrderSide,
    OrderStatus,
)
from execution_engine.simulation.slippage_model import SlippageModel, SlippageConfig
from execution_engine.simulation.spread_model import SpreadModel, SpreadConfig
from execution_engine.simulation.liquidity_model import LiquidityModel, LiquidityConfig
from execution_engine.simulation.partial_fill_model import PartialFillModel, PartialFillConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FillSimulatorConfig:
    slippage: SlippageConfig = field(default_factory=SlippageConfig)
    spread: SpreadConfig = field(default_factory=SpreadConfig)
    liquidity: LiquidityConfig = field(default_factory=LiquidityConfig)
    partial_fill: PartialFillConfig = field(default_factory=PartialFillConfig)
    latency_mean_ms: float = 50.0
    latency_std_ms: float = 20.0
    min_latency_ms: float = 5.0
    commission_per_share: float = 0.005
    commission_min: float = 1.0
    random_seed: int | None = 42


class FillSimulator:
    """
    Simulate realistic fills for child orders.

    Combines multiple friction models to produce fills that reflect
    institutional execution reality.
    """

    def __init__(self, config: FillSimulatorConfig | None = None) -> None:
        self._config = config or FillSimulatorConfig()
        self._slippage = SlippageModel(self._config.slippage)
        self._spread = SpreadModel(self._config.spread)
        self._liquidity = LiquidityModel(self._config.liquidity)
        self._partial_fill = PartialFillModel(self._config.partial_fill)
        self._rng = np.random.default_rng(self._config.random_seed)

    def simulate_fill(
        self,
        child: ChildOrder,
        market_price: float,
        volatility: float = 0.02,
        daily_volume: float = 1_000_000.0,
        timestamp: pd.Timestamp | None = None,
    ) -> FillEvent | None:
        """
        Simulate a fill for a single child order.

        Returns None if the order is fully rejected (e.g., zero liquidity).
        """
        cfg = self._config
        ts = timestamp or pd.Timestamp.now(tz="UTC")

        if market_price <= 0 or not np.isfinite(market_price):
            logger.warning("Invalid market price %.4f for %s", market_price, child.symbol)
            child.status = OrderStatus.REJECTED
            return None

        if child.quantity <= 0 or not np.isfinite(child.quantity):
            logger.warning("Invalid quantity %.4f for %s", child.quantity, child.symbol)
            child.status = OrderStatus.REJECTED
            return None

        fill_qty, is_partial = self._partial_fill.compute(
            order_quantity=child.quantity,
            daily_volume=daily_volume,
            volatility=volatility,
        )

        if fill_qty <= 0:
            child.status = OrderStatus.REJECTED
            return None

        liq_available = self._liquidity.available_liquidity(
            order_quantity=fill_qty,
            daily_volume=daily_volume,
            participation_rate=child.metadata.get("target_participation", 0.05),
        )
        fill_qty = min(fill_qty, liq_available)
        if fill_qty <= 0:
            child.status = OrderStatus.REJECTED
            return None

        spread_bps = self._spread.compute(
            volatility=volatility,
            daily_volume=daily_volume,
            order_size=fill_qty,
        )

        slippage_bps = self._slippage.compute(
            order_size=fill_qty,
            daily_volume=daily_volume,
            volatility=volatility,
            side=child.side,
        )

        impact_bps = self._compute_impact(
            fill_qty, daily_volume, volatility,
        )

        total_friction_bps = spread_bps + slippage_bps + impact_bps

        if child.side == OrderSide.BUY:
            fill_price = market_price * (1 + total_friction_bps / 10_000)
        else:
            fill_price = market_price * (1 - total_friction_bps / 10_000)

        fill_price = max(fill_price, 1e-6)

        latency = max(
            cfg.min_latency_ms,
            self._rng.normal(cfg.latency_mean_ms, cfg.latency_std_ms),
        )

        commission = max(
            cfg.commission_min,
            fill_qty * cfg.commission_per_share,
        )

        notional = fill_qty * fill_price
        total_cost = (
            notional * total_friction_bps / 10_000 + commission
        )

        return FillEvent(
            child_id=child.child_id,
            symbol=child.symbol,
            side=child.side,
            quantity_filled=fill_qty,
            fill_price=fill_price,
            arrival_price=market_price,
            slippage_bps=slippage_bps,
            spread_cost_bps=spread_bps,
            market_impact_bps=impact_bps,
            commission=commission,
            total_cost=total_cost,
            timestamp=ts + pd.Timedelta(milliseconds=latency),
            latency_ms=latency,
            venue="simulated",
        )

    def _compute_impact(
        self,
        order_size: float,
        daily_volume: float,
        volatility: float,
    ) -> float:
        """
        Square-root market impact model.

        Impact ~ σ * sqrt(Q/V) where Q = order size, V = daily volume.
        Based on Almgren & Chriss (2000) permanent impact estimate.
        """
        if daily_volume <= 0:
            return 50.0

        participation = order_size / daily_volume
        impact = volatility * np.sqrt(participation) * 10_000
        impact = min(impact, 100.0)
        return float(impact)
