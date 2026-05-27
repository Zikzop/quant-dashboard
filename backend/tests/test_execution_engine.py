"""
Execution engine tests — validates execution pipeline from order to fill.

Tests cover:
- Base types and validation
- Execution algorithms (TWAP, VWAP, participation, iceberg)
- Fill simulation (slippage, spread, impact, partial fills)
- Scheduling (queue, lifecycle, clock)
- Routing (gateway validation, venue selection)
- Quality analytics (slippage, IS, latency, benchmarks)
- Orchestrator end-to-end
"""

import numpy as np
import pandas as pd
import pytest


class TestExecutionBase:
    def test_parent_order_validation(self):
        from execution_engine.execution_base import ParentOrder, OrderSide

        order = ParentOrder(
            symbol="AAPL",
            side=OrderSide.BUY,
            total_quantity=1000.0,
        )
        assert order.total_quantity == 1000.0
        assert order.symbol == "AAPL"

    def test_parent_order_rejects_nan_quantity(self):
        from execution_engine.execution_base import ParentOrder

        with pytest.raises(ValueError, match="positive finite"):
            ParentOrder(symbol="AAPL", total_quantity=float("nan"))

    def test_parent_order_rejects_zero_quantity(self):
        from execution_engine.execution_base import ParentOrder

        with pytest.raises(ValueError, match="positive finite"):
            ParentOrder(symbol="AAPL", total_quantity=0.0)

    def test_fill_event_validation(self):
        from execution_engine.execution_base import FillEvent, OrderSide

        fill = FillEvent(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity_filled=100.0,
            fill_price=150.0,
            arrival_price=149.5,
        )
        assert fill.notional == 15000.0
        assert fill.implementation_shortfall_bps > 0

    def test_fill_event_rejects_negative_price(self):
        from execution_engine.execution_base import FillEvent

        with pytest.raises(ValueError, match="positive finite"):
            FillEvent(symbol="AAPL", fill_price=-10.0)

    def test_child_order_apply_fill(self):
        from execution_engine.execution_base import (
            ChildOrder,
            FillEvent,
            OrderSide,
            OrderStatus,
        )

        child = ChildOrder(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            status=OrderStatus.ACTIVE,
        )
        fill = FillEvent(
            child_id=child.child_id,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity_filled=100.0,
            fill_price=150.0,
            arrival_price=150.0,
        )
        child.apply_fill(fill)
        assert child.status == OrderStatus.FILLED
        assert abs(child.fill_ratio - 1.0) < 1e-8

    def test_execution_result_aggregation(self):
        from execution_engine.execution_base import (
            ChildOrder,
            ExecutionResult,
            FillEvent,
            OrderSide,
            OrderStatus,
            ParentOrder,
        )

        parent = ParentOrder(symbol="AAPL", total_quantity=200.0)
        child1 = ChildOrder(parent_id=parent.order_id, symbol="AAPL", quantity=100.0)
        child2 = ChildOrder(parent_id=parent.order_id, symbol="AAPL", quantity=100.0)

        f1 = FillEvent(
            child_id=child1.child_id, symbol="AAPL",
            quantity_filled=100.0, fill_price=150.0, arrival_price=149.0,
            slippage_bps=3.0, spread_cost_bps=2.0,
        )
        f2 = FillEvent(
            child_id=child2.child_id, symbol="AAPL",
            quantity_filled=100.0, fill_price=151.0, arrival_price=149.0,
            slippage_bps=5.0, spread_cost_bps=2.0,
        )
        child1.apply_fill(f1)
        child2.apply_fill(f2)

        result = ExecutionResult(parent_order=parent, child_orders=[child1, child2])
        result.aggregate_from_children()

        assert result.total_filled == 200.0
        assert abs(result.fill_ratio - 1.0) < 1e-8
        assert result.avg_fill_price == 150.5


class TestExecutionAlgorithms:
    def test_twap_schedule(self):
        from execution_engine.algorithms.twap_execution import TWAPAlgorithm
        from execution_engine.execution_base import ParentOrder

        parent = ParentOrder(symbol="AAPL", total_quantity=1000.0)
        algo = TWAPAlgorithm()
        schedule = algo.generate_schedule(parent, n_slices=10)

        assert schedule.n_slices == 10
        assert len(schedule.slices) == 10
        total_qty = sum(c.quantity for c in schedule.slices)
        assert abs(total_qty - 1000.0) < 1.0

        times = [c.scheduled_time for c in schedule.slices]
        assert all(t1 <= t2 for t1, t2 in zip(times, times[1:]))

    def test_vwap_schedule(self):
        from execution_engine.algorithms.vwap_execution import VWAPAlgorithm
        from execution_engine.execution_base import ParentOrder

        parent = ParentOrder(symbol="AAPL", total_quantity=1000.0)
        algo = VWAPAlgorithm()
        schedule = algo.generate_schedule(parent)

        assert schedule.n_buckets == 20
        total_qty = sum(c.quantity for c in schedule.slices)
        assert abs(total_qty - 1000.0) < 10.0

    def test_participation_schedule(self):
        from execution_engine.algorithms.participation_execution import (
            ParticipationAlgorithm,
        )
        from execution_engine.execution_base import ParentOrder

        parent = ParentOrder(symbol="AAPL", total_quantity=5000.0)
        algo = ParticipationAlgorithm()
        schedule = algo.generate_schedule(parent, expected_daily_volume=1_000_000.0)

        assert schedule.target_participation > 0
        assert schedule.completion_probability > 0

    def test_iceberg_initial(self):
        from execution_engine.algorithms.iceberg_execution import IcebergAlgorithm
        from execution_engine.execution_base import ParentOrder

        parent = ParentOrder(symbol="AAPL", total_quantity=10000.0)
        algo = IcebergAlgorithm()
        schedule = algo.generate_initial(parent, current_price=150.0)

        assert schedule.visible_quantity < schedule.total_quantity
        assert schedule.hidden_quantity > 0
        assert schedule.initial_slice.quantity > 0


class TestFillSimulation:
    def test_fill_simulator_basic(self):
        from execution_engine.simulation.fill_simulator import FillSimulator
        from execution_engine.execution_base import ChildOrder, OrderSide, OrderStatus

        sim = FillSimulator()
        child = ChildOrder(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100.0,
            status=OrderStatus.ACTIVE,
        )
        fill = sim.simulate_fill(
            child,
            market_price=150.0,
            volatility=0.02,
            daily_volume=1_000_000.0,
        )

        assert fill is not None
        assert fill.fill_price > 0
        assert fill.quantity_filled > 0
        assert fill.slippage_bps >= 0
        assert fill.spread_cost_bps >= 0
        assert fill.commission > 0
        assert fill.latency_ms > 0

    def test_fill_simulator_no_perfect_fills(self):
        from execution_engine.simulation.fill_simulator import FillSimulator
        from execution_engine.execution_base import ChildOrder, OrderSide, OrderStatus

        sim = FillSimulator()
        fills = []
        for _ in range(20):
            child = ChildOrder(
                symbol="AAPL", side=OrderSide.BUY,
                quantity=100.0, status=OrderStatus.ACTIVE,
            )
            fill = sim.simulate_fill(child, market_price=150.0)
            if fill:
                fills.append(fill)

        assert all(f.fill_price != 150.0 for f in fills)
        assert all(f.total_cost > 0 for f in fills)

    def test_fill_rejects_invalid_price(self):
        from execution_engine.simulation.fill_simulator import FillSimulator
        from execution_engine.execution_base import ChildOrder, OrderSide, OrderStatus

        sim = FillSimulator()
        child = ChildOrder(
            symbol="AAPL", side=OrderSide.BUY,
            quantity=100.0, status=OrderStatus.ACTIVE,
        )
        fill = sim.simulate_fill(child, market_price=-10.0)
        assert fill is None
        assert child.status == OrderStatus.REJECTED

    def test_slippage_model(self):
        from execution_engine.simulation.slippage_model import SlippageModel, SlippageConfig

        model = SlippageModel(SlippageConfig(max_slippage_bps=200.0))
        small = model.compute(order_size=100, daily_volume=1_000_000)
        large = model.compute(order_size=100_000, daily_volume=1_000_000)
        assert large >= small
        assert small > 0

    def test_spread_model(self):
        from execution_engine.simulation.spread_model import SpreadModel, SpreadConfig

        model = SpreadModel(SpreadConfig(random_seed=None))
        low_vol_vals = [model.compute(volatility=0.005, daily_volume=10_000_000) for _ in range(20)]
        high_vol_vals = [model.compute(volatility=0.08, daily_volume=10_000_000) for _ in range(20)]
        assert np.mean(high_vol_vals) > np.mean(low_vol_vals)

    def test_liquidity_model(self):
        from execution_engine.simulation.liquidity_model import LiquidityModel

        model = LiquidityModel()
        small_avail = model.available_liquidity(100, 1_000_000)
        large_avail = model.available_liquidity(500_000, 1_000_000)
        assert small_avail >= 100
        assert large_avail < 500_000

    def test_partial_fill_model(self):
        from execution_engine.simulation.partial_fill_model import PartialFillModel

        model = PartialFillModel()
        qty, is_partial = model.compute(100.0, 1_000_000.0)
        assert qty > 0
        assert qty <= 100.0


class TestScheduling:
    def test_execution_clock(self):
        from execution_engine.scheduling.execution_clock import (
            ExecutionClock,
            MarketSession,
        )

        clock = ExecutionClock(simulation_mode=True)
        ts = pd.Timestamp("2024-06-03 10:30:00", tz="America/New_York")
        clock.advance_to(ts)
        assert clock.now == ts

    def test_clock_rejects_backwards(self):
        from execution_engine.scheduling.execution_clock import ExecutionClock

        clock = ExecutionClock(simulation_mode=True)
        t1 = pd.Timestamp("2024-06-03 10:00:00", tz="UTC")
        t2 = pd.Timestamp("2024-06-03 09:00:00", tz="UTC")
        clock.advance_to(t1)
        with pytest.raises(ValueError, match="backwards"):
            clock.advance_to(t2)

    def test_execution_queue_priority(self):
        from execution_engine.scheduling.execution_queue import ExecutionQueue
        from execution_engine.execution_base import (
            ParentOrder,
            ExecutionUrgency,
        )

        queue = ExecutionQueue()
        low = ParentOrder(symbol="AAPL", total_quantity=100.0, urgency=ExecutionUrgency.LOW)
        high = ParentOrder(symbol="MSFT", total_quantity=100.0, urgency=ExecutionUrgency.HIGH)

        queue.submit(low)
        queue.submit(high)
        first = queue.next()
        assert first is not None
        assert first.urgency == ExecutionUrgency.HIGH

    def test_queue_rejects_duplicate_symbol(self):
        from execution_engine.scheduling.execution_queue import ExecutionQueue
        from execution_engine.execution_base import ParentOrder

        queue = ExecutionQueue()
        o1 = ParentOrder(symbol="AAPL", total_quantity=100.0)
        queue.submit(o1)
        queue.next()

        o2 = ParentOrder(symbol="AAPL", total_quantity=200.0)
        assert not queue.submit(o2)

    def test_order_lifecycle(self):
        from execution_engine.scheduling.order_lifecycle import OrderLifecycleManager
        from execution_engine.execution_base import ParentOrder, OrderStatus

        mgr = OrderLifecycleManager()
        parent = ParentOrder(symbol="AAPL", total_quantity=100.0)
        mgr.register(parent)

        ts = pd.Timestamp.now(tz="UTC")
        assert mgr.transition(parent.order_id, OrderStatus.ACTIVE, ts)
        assert mgr.transition(parent.order_id, OrderStatus.FILLED, ts)
        assert not mgr.transition(parent.order_id, OrderStatus.ACTIVE, ts)

        history = mgr.get_history(parent.order_id)
        assert len(history) == 3


class TestRouting:
    def test_gateway_accepts_valid(self):
        from execution_engine.routing.execution_gateway import ExecutionGateway
        from execution_engine.execution_base import ParentOrder

        gateway = ExecutionGateway()
        order = ParentOrder(symbol="AAPL", total_quantity=100.0)
        result = gateway.submit(order, market_price=150.0)
        assert result.accepted

    def test_gateway_rejects_nan(self):
        from execution_engine.routing.execution_gateway import ExecutionGateway
        from execution_engine.execution_base import ParentOrder, OrderSide

        gateway = ExecutionGateway()
        with pytest.raises(ValueError):
            order = ParentOrder(symbol="AAPL", total_quantity=float("nan"))

    def test_venue_selection(self):
        from execution_engine.routing.venue_selection import VenueSelector
        from execution_engine.execution_base import ParentOrder, ExecutionAlgorithm

        selector = VenueSelector()
        large_order = ParentOrder(symbol="AAPL", total_quantity=100_000.0)
        rec = selector.select(large_order, daily_volume=1_000_000.0)
        assert rec.recommended_algorithm in (
            ExecutionAlgorithm.TWAP,
            ExecutionAlgorithm.VWAP,
        )


class TestExecutionQuality:
    def _make_result(self):
        from execution_engine.execution_base import (
            ChildOrder,
            ExecutionResult,
            FillEvent,
            OrderSide,
            OrderStatus,
            ParentOrder,
        )

        parent = ParentOrder(symbol="AAPL", total_quantity=1000.0)
        child = ChildOrder(parent_id=parent.order_id, symbol="AAPL", quantity=1000.0)

        fill = FillEvent(
            child_id=child.child_id,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity_filled=1000.0,
            fill_price=150.5,
            arrival_price=150.0,
            slippage_bps=5.0,
            spread_cost_bps=2.0,
            market_impact_bps=3.0,
            commission=5.0,
            total_cost=25.0,
            latency_ms=45.0,
        )
        child.apply_fill(fill)
        result = ExecutionResult(parent_order=parent, child_orders=[child])
        result.aggregate_from_children()
        return result

    def test_slippage_analysis(self):
        from execution_engine.quality.slippage_analysis import SlippageAnalyzer

        result = self._make_result()
        analyzer = SlippageAnalyzer()
        report = analyzer.analyze(result)
        assert report.total_slippage_bps > 0
        assert report.n_fills == 1

    def test_implementation_shortfall(self):
        from execution_engine.quality.implementation_shortfall import (
            ImplementationShortfallAnalyzer,
        )

        result = self._make_result()
        analyzer = ImplementationShortfallAnalyzer()
        report = analyzer.analyze(result, decision_price=150.0)
        assert report.total_is_bps > 0

    def test_latency_monitor(self):
        from execution_engine.quality.latency_monitor import LatencyMonitor

        result = self._make_result()
        monitor = LatencyMonitor()
        report = monitor.analyze(result)
        assert report.mean_latency_ms > 0

    def test_execution_quality_report(self):
        from execution_engine.quality.execution_quality_report import (
            ExecutionQualityAnalyzer,
        )

        result = self._make_result()
        analyzer = ExecutionQualityAnalyzer()
        report = analyzer.analyze(result, decision_price=150.0)
        assert 0 <= report.overall_score <= 100
        assert report.grade in ("A", "B", "C", "D", "F")


class TestOrchestrator:
    def test_execution_orchestrator_end_to_end(self):
        from execution_engine.orchestration.execution_orchestrator import (
            ExecutionOrchestrator,
        )
        from execution_engine.execution_base import (
            ParentOrder,
            OrderSide,
            ExecutionAlgorithm,
            OrderStatus,
        )

        orchestrator = ExecutionOrchestrator()
        parent = ParentOrder(
            symbol="AAPL",
            side=OrderSide.BUY,
            total_quantity=1000.0,
            algorithm=ExecutionAlgorithm.TWAP,
        )

        result = orchestrator.execute(
            parent_order=parent,
            market_price=150.0,
            daily_volume=1_000_000.0,
            volatility=0.02,
        )

        assert result.total_filled > 0
        assert result.avg_fill_price > 0
        assert result.status in (OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED)

        quality = orchestrator.last_quality_report
        assert quality is not None
        assert quality.overall_score > 0

    def test_orchestrator_batch_execution(self):
        from execution_engine.orchestration.execution_orchestrator import (
            ExecutionOrchestrator,
        )
        from execution_engine.execution_base import ParentOrder, OrderSide

        orchestrator = ExecutionOrchestrator()
        orders = [
            (
                ParentOrder(symbol=f"SYM_{i}", side=OrderSide.BUY, total_quantity=500.0),
                100.0 + i * 10,
                500_000.0,
                0.02,
            )
            for i in range(3)
        ]

        results = orchestrator.execute_batch(orders)
        assert len(results) == 3
        assert all(r.total_filled > 0 for r in results)

    def test_orchestrator_rejects_invalid(self):
        from execution_engine.orchestration.execution_orchestrator import (
            ExecutionOrchestrator,
        )
        from execution_engine.execution_base import ParentOrder, OrderSide, OrderStatus

        orchestrator = ExecutionOrchestrator()
        parent = ParentOrder(symbol="", side=OrderSide.BUY, total_quantity=100.0)
        result = orchestrator.execute(parent, market_price=150.0)
        assert result.status == OrderStatus.REJECTED
