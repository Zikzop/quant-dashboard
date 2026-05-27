"""
Execution orchestrator — coordinates the full execution pipeline.

Sequence:
1. Receive parent order from portfolio engine
2. Validate through gateway
3. Select venue and algorithm
4. Generate child order schedule
5. Execute (async or sync) through fill simulator
6. Aggregate results
7. Compute execution quality metrics
8. Return execution result

This is the top-level entry point for the execution engine.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from execution_engine.execution_base import (
    ChildOrder,
    ExecutionAlgorithm,
    ExecutionResult,
    FillEvent,
    OrderSide,
    OrderStatus,
    ParentOrder,
)
from execution_engine.algorithms.twap_execution import TWAPAlgorithm, TWAPConfig
from execution_engine.algorithms.vwap_execution import VWAPAlgorithm, VWAPConfig
from execution_engine.algorithms.participation_execution import (
    ParticipationAlgorithm,
    ParticipationConfig,
)
from execution_engine.algorithms.iceberg_execution import IcebergAlgorithm, IcebergConfig
from execution_engine.simulation.fill_simulator import FillSimulator, FillSimulatorConfig
from execution_engine.scheduling.async_scheduler import SyncExecutionScheduler
from execution_engine.scheduling.execution_clock import ExecutionClock
from execution_engine.scheduling.order_lifecycle import OrderLifecycleManager
from execution_engine.scheduling.execution_queue import ExecutionQueue
from execution_engine.routing.execution_gateway import ExecutionGateway, GatewayConfig
from execution_engine.routing.venue_selection import VenueSelector
from execution_engine.quality.execution_quality_report import (
    ExecutionQualityAnalyzer,
    ExecutionQualityReport,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExecutionOrchestratorConfig:
    fill_simulator: FillSimulatorConfig = field(default_factory=FillSimulatorConfig)
    gateway: GatewayConfig = field(default_factory=GatewayConfig)
    twap: TWAPConfig = field(default_factory=TWAPConfig)
    vwap: VWAPConfig = field(default_factory=VWAPConfig)
    participation: ParticipationConfig = field(default_factory=ParticipationConfig)
    iceberg: IcebergConfig = field(default_factory=IcebergConfig)
    simulation_mode: bool = True
    analyze_quality: bool = True


class ExecutionOrchestrator:
    """
    Full execution pipeline orchestrator.

    Usage:
        orchestrator = ExecutionOrchestrator(config)
        result = orchestrator.execute(
            parent_order=order,
            market_price=100.0,
            daily_volume=1_000_000.0,
            volatility=0.02,
        )
        quality = orchestrator.last_quality_report
    """

    def __init__(self, config: ExecutionOrchestratorConfig | None = None) -> None:
        self._config = config or ExecutionOrchestratorConfig()
        cfg = self._config

        self._fill_sim = FillSimulator(cfg.fill_simulator)
        self._gateway = ExecutionGateway(cfg.gateway)
        self._venue_selector = VenueSelector()
        self._lifecycle = OrderLifecycleManager()
        self._queue = ExecutionQueue()
        self._clock = ExecutionClock(simulation_mode=cfg.simulation_mode)
        self._scheduler = SyncExecutionScheduler(self._clock)
        self._quality_analyzer = ExecutionQualityAnalyzer()

        self._twap = TWAPAlgorithm(cfg.twap)
        self._vwap = VWAPAlgorithm(cfg.vwap)
        self._participation = ParticipationAlgorithm(cfg.participation)
        self._iceberg = IcebergAlgorithm(cfg.iceberg)

        self._last_quality: ExecutionQualityReport | None = None

    @property
    def last_quality_report(self) -> ExecutionQualityReport | None:
        return self._last_quality

    def execute(
        self,
        parent_order: ParentOrder,
        market_price: float,
        daily_volume: float = 1_000_000.0,
        volatility: float = 0.02,
        historical_volumes: pd.DataFrame | None = None,
        timestamp: pd.Timestamp | None = None,
    ) -> ExecutionResult:
        """
        Execute a parent order through the full pipeline.

        Parameters
        ----------
        parent_order : the portfolio-level order intent
        market_price : current market price (arrival price)
        daily_volume : estimated average daily volume
        volatility : current asset volatility (daily)
        historical_volumes : intraday volume data for VWAP
        timestamp : execution start timestamp
        """
        ts = timestamp or pd.Timestamp.now(tz="UTC")
        warnings: list[str] = []

        submission = self._gateway.submit(parent_order, market_price)
        if not submission.accepted:
            result = ExecutionResult(
                parent_order=parent_order,
                status=OrderStatus.REJECTED,
                warnings=[f"Rejected: {submission.rejection_reason}"],
            )
            return result

        warnings.extend(submission.warnings)

        venue = self._venue_selector.select(
            parent_order, daily_volume, volatility,
        )
        warnings.extend(venue.warnings)

        algo = parent_order.algorithm
        if algo == ExecutionAlgorithm.IMMEDIATE:
            algo = ExecutionAlgorithm.TWAP

        children = self._generate_children(
            parent_order, algo, ts, historical_volumes, daily_volume,
            market_price,
        )
        warnings_from_gen = [
            w for child in children for w in child.metadata.get("warnings", [])
        ]
        warnings.extend(warnings_from_gen)

        exec_result = self._lifecycle.register(parent_order)
        exec_result.child_orders = children
        self._lifecycle.transition(
            parent_order.order_id, OrderStatus.ACTIVE, ts, "execution started",
        )

        if self._clock._simulation_mode:
            self._clock._simulated_time = ts

        def fill_handler(child: ChildOrder) -> FillEvent | None:
            return self._fill_sim.simulate_fill(
                child,
                market_price=market_price,
                volatility=volatility,
                daily_volume=daily_volume,
                timestamp=child.scheduled_time or ts,
            )

        fills = self._scheduler.execute_all(children, fill_handler)

        exec_result.aggregate_from_children()
        exec_result.warnings.extend(warnings)

        final_status = OrderStatus.FILLED if exec_result.fill_ratio >= 0.99 else (
            OrderStatus.PARTIALLY_FILLED if exec_result.fill_ratio > 0 else OrderStatus.REJECTED
        )
        self._lifecycle.transition(
            parent_order.order_id, final_status, ts, "execution completed",
        )
        exec_result.status = final_status

        if self._config.analyze_quality and fills:
            self._last_quality = self._quality_analyzer.analyze(
                exec_result,
                decision_price=market_price,
            )

        return exec_result

    def _generate_children(
        self,
        parent: ParentOrder,
        algo: ExecutionAlgorithm,
        timestamp: pd.Timestamp,
        historical_volumes: pd.DataFrame | None,
        daily_volume: float,
        market_price: float,
    ) -> list[ChildOrder]:
        if algo == ExecutionAlgorithm.TWAP:
            schedule = self._twap.generate_schedule(parent, start_time=timestamp)
            return schedule.slices

        elif algo == ExecutionAlgorithm.VWAP:
            schedule = self._vwap.generate_schedule(
                parent, historical_volumes=historical_volumes,
                start_time=timestamp,
            )
            return schedule.slices

        elif algo == ExecutionAlgorithm.PARTICIPATION:
            schedule = self._participation.generate_schedule(
                parent,
                expected_daily_volume=daily_volume,
                start_time=timestamp,
            )
            return schedule.slices

        elif algo == ExecutionAlgorithm.ICEBERG:
            ice_schedule = self._iceberg.generate_initial(
                parent, current_price=market_price, start_time=timestamp,
            )
            return [ice_schedule.initial_slice]

        else:
            schedule = self._twap.generate_schedule(parent, start_time=timestamp)
            return schedule.slices

    def execute_batch(
        self,
        orders: list[tuple[ParentOrder, float, float, float]],
        timestamp: pd.Timestamp | None = None,
    ) -> list[ExecutionResult]:
        """
        Execute multiple parent orders.

        Parameters
        ----------
        orders : list of (parent_order, market_price, daily_volume, volatility)
        """
        results = []
        for parent, price, volume, vol in orders:
            result = self.execute(
                parent, price, volume, vol, timestamp=timestamp,
            )
            results.append(result)
        return results
