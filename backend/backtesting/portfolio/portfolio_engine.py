"""
Portfolio engine — orchestrates signal-to-order conversion with risk constraints.

This is the decision layer between alpha signals and execution:
1. Receives SignalEvents
2. Computes target positions via position sizing
3. Checks leverage and exposure constraints
4. Checks turnover limits
5. Emits OrderEvents for the delta between current and target positions
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.event_engine.events import (
    Event,
    FillEvent,
    FillStatus,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderType,
    PortfolioUpdateEvent,
    RiskUpdateEvent,
    SignalEvent,
)
from backtesting.execution.execution_report import ExecutionReport
from backtesting.execution.fill_simulator import FillSimulator, MarketSnapshot
from backtesting.portfolio.exposure_engine import ExposureEngine
from backtesting.portfolio.leverage_constraints import LeverageConstraints
from backtesting.portfolio.pnl_engine import PnLEngine
from backtesting.portfolio.portfolio_state import PortfolioState
from backtesting.portfolio.position_sizing import PositionSizer, VolatilityTargetSizer
from backtesting.portfolio.turnover_engine import TurnoverEngine
from backtesting.simulation_config import SimulationConfig

logger = logging.getLogger(__name__)


class PortfolioEngine:
    """
    Central portfolio management engine.

    Handles the full lifecycle:
    MarketEvent -> price update
    SignalEvent -> target computation -> order generation
    FillEvent -> position update -> PnL recording -> risk update
    """

    def __init__(
        self,
        config: SimulationConfig | None = None,
        position_sizer: PositionSizer | None = None,
    ) -> None:
        cfg = config or SimulationConfig()
        self._state = PortfolioState(cfg.portfolio.initial_capital)
        self._sizer = position_sizer or VolatilityTargetSizer(
            target_volatility=cfg.portfolio.target_volatility or 0.15,
            max_weight=cfg.portfolio.max_position_weight,
        )
        self._constraints = LeverageConstraints(
            max_gross_leverage=cfg.portfolio.max_gross_leverage,
            max_position_weight=cfg.portfolio.max_position_weight,
            max_net_exposure_ratio=cfg.portfolio.max_net_exposure,
        )
        self._exposure = ExposureEngine()
        self._turnover = TurnoverEngine()
        self._pnl = PnLEngine()
        self._exec_report = ExecutionReport()

        self._max_daily_turnover = cfg.portfolio.max_turnover_daily
        self._min_trade_size = cfg.portfolio.min_trade_size
        self._rebalance_threshold = cfg.portfolio.rebalance_threshold

        self._market_data: dict[str, MarketSnapshot] = {}
        self._volatilities: dict[str, float] = {}
        self._period_costs: dict[str, float] = {
            "slippage": 0.0,
            "spread": 0.0,
            "commission": 0.0,
            "impact": 0.0,
        }

    @property
    def state(self) -> PortfolioState:
        return self._state

    @property
    def pnl_engine(self) -> PnLEngine:
        return self._pnl

    @property
    def turnover_engine(self) -> TurnoverEngine:
        return self._turnover

    @property
    def execution_report(self) -> ExecutionReport:
        return self._exec_report

    def on_market(self, event: MarketEvent) -> list[Event] | None:
        """Update market prices from MarketEvent."""
        snap = MarketSnapshot(
            price=event.close,
            bid=event.bid,
            ask=event.ask,
            volume=event.volume,
            volatility=self._volatilities.get(event.symbol, 0.02),
            avg_volume=event.volume,
        )
        self._market_data[event.symbol] = snap
        self._state.update_prices({event.symbol: event.close})
        return None

    def on_signal(self, event: SignalEvent) -> list[Event] | None:
        """Convert signal to order(s) after applying constraints."""
        snapshot = self._market_data.get(event.symbol)
        if snapshot is None:
            logger.warning("No market data for %s, skipping signal", event.symbol)
            return None

        current_pos = self._state.get_position(event.symbol)
        target_qty = self._sizer.size(
            alpha_score=event.alpha_score,
            confidence=event.confidence,
            price=snapshot.price,
            volatility=snapshot.volatility,
            portfolio_value=self._state.portfolio_value,
            current_position=current_pos.quantity,
        )

        delta = target_qty - current_pos.quantity

        if abs(delta * snapshot.price) < self._min_trade_size:
            return None

        current_weight = abs(current_pos.market_value) / max(
            self._state.portfolio_value, 1e-9
        )
        target_weight = abs(target_qty * snapshot.price) / max(
            self._state.portfolio_value, 1e-9
        )
        if abs(target_weight - current_weight) < self._rebalance_threshold:
            return None

        proposed_notional = abs(delta * snapshot.price)
        if not self._turnover.can_trade(
            event.timestamp,
            proposed_notional,
            self._state.portfolio_value,
            self._max_daily_turnover,
        ):
            logger.debug("Turnover limit blocks trade on %s", event.symbol)
            return None

        delta = self._constraints.scale_order(
            self._state, event.symbol, delta, snapshot.price
        )

        if abs(delta) < 1e-9:
            return None

        side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        order = OrderEvent(
            timestamp=event.timestamp,
            symbol=event.symbol,
            side=side,
            quantity=abs(delta),
            signal_event_id=event.event_id,
        )
        return [order]

    def on_fill(self, event: FillEvent) -> list[Event] | None:
        """Process fill: update positions, PnL, and emit portfolio/risk updates."""
        self._exec_report.record(event)

        if event.fill_status == FillStatus.REJECTED:
            return None

        signed_qty = event.quantity_filled
        if event.side == OrderSide.SELL:
            signed_qty = -signed_qty

        realized = self._state.apply_fill(
            symbol=event.symbol,
            quantity=signed_qty,
            fill_price=event.fill_price,
            costs=event.total_cost,
        )

        notional = abs(event.quantity_filled * event.fill_price)
        self._turnover.record_trade(event.timestamp, notional)

        self._period_costs["slippage"] += event.slippage
        self._period_costs["spread"] += event.spread_cost
        self._period_costs["commission"] += event.commission
        self._period_costs["impact"] += event.market_impact

        pos = self._state.get_position(event.symbol)
        pv = self._state.portfolio_value
        weight = pos.market_value / pv if pv > 0 else 0.0

        portfolio_update = PortfolioUpdateEvent(
            timestamp=event.timestamp,
            symbol=event.symbol,
            new_position=pos.quantity,
            new_weight=weight,
            portfolio_value=pv,
            cash=self._state.cash,
            fill_event_id=event.event_id,
        )

        exposure = self._exposure.compute(self._state)
        violations = self._exposure.check_constraints(
            self._state,
            self._constraints.max_gross_leverage,
            self._constraints.max_net_exposure_ratio,
            self._constraints.max_position_weight,
        )

        risk_update = RiskUpdateEvent(
            timestamp=event.timestamp,
            gross_exposure=exposure.gross_exposure,
            net_exposure=exposure.net_exposure,
            leverage=exposure.gross_leverage,
            max_position_weight=exposure.max_position_weight,
            drawdown=self._state.drawdown,
            constraint_violations=tuple(violations),
        )

        return [portfolio_update, risk_update]

    def record_period_pnl(self, timestamp: pd.Timestamp) -> None:
        """Snapshot PnL at end of period (typically end of day)."""
        self._pnl.record(
            timestamp=timestamp,
            portfolio_value=self._state.portfolio_value,
            cash=self._state.cash,
            realized_pnl=self._state.total_realized_pnl,
            unrealized_pnl=self._state.total_unrealized_pnl,
            slippage_cost=self._period_costs["slippage"],
            spread_cost=self._period_costs["spread"],
            commission_cost=self._period_costs["commission"],
            impact_cost=self._period_costs["impact"],
        )
        self._period_costs = {k: 0.0 for k in self._period_costs}

    def update_volatility(self, symbol: str, vol: float) -> None:
        self._volatilities[symbol] = vol

    def get_snapshot(self, symbol: str) -> MarketSnapshot | None:
        return self._market_data.get(symbol)
