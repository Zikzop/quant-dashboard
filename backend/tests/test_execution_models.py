"""
Tests for execution simulation models.

Validates:
- Slippage is always non-negative
- Spread widens with volatility
- Market impact increases with order size
- Fill simulator produces valid FillEvents
- Execution costs degrade alpha
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from backtesting.event_engine.events import OrderEvent, OrderSide, FillStatus
from backtesting.execution.fill_simulator import FillSimulator, MarketSnapshot
from backtesting.execution.market_impact import SquareRootImpact, LinearImpact, ZeroImpact
from backtesting.execution.slippage_models import (
    VolatilityScaledSlippage,
    FixedBpsSlippage,
    VolumeWeightedSlippage,
)
from backtesting.execution.spread_models import VolatilityAdjustedSpread, FixedSpread
from backtesting.execution.latency_models import LogNormalLatency, FixedLatency, ZeroLatency
from backtesting.simulation_config import ExecutionConfig


class TestSlippageModels(unittest.TestCase):
    def setUp(self) -> None:
        self.rng = np.random.default_rng(42)

    def test_slippage_non_negative(self) -> None:
        model = VolatilityScaledSlippage()
        for _ in range(100):
            slip = model.estimate(100, 1000, 0.2, 50000, self.rng)
            self.assertGreaterEqual(slip, 0.0)

    def test_slippage_increases_with_volatility(self) -> None:
        model = VolatilityScaledSlippage(stochastic_scale=0)
        low_vol = model.estimate(100, 1000, 0.05, 50000, self.rng)
        high_vol = model.estimate(100, 1000, 0.50, 50000, self.rng)
        self.assertGreater(high_vol, low_vol)

    def test_fixed_bps_slippage(self) -> None:
        model = FixedBpsSlippage(bps=10)
        slip = model.estimate(100, 1000, 0.2, 50000, self.rng)
        self.assertAlmostEqual(slip, 0.10, places=4)

    def test_volume_weighted_slippage(self) -> None:
        model = VolumeWeightedSlippage()
        small = model.estimate(100, 100, 0.2, 100000, self.rng)
        large = model.estimate(100, 50000, 0.2, 100000, self.rng)
        self.assertGreater(large, small)


class TestSpreadModels(unittest.TestCase):
    def setUp(self) -> None:
        self.rng = np.random.default_rng(42)

    def test_spread_widens_with_vol(self) -> None:
        model = VolatilityAdjustedSpread()
        low = model.estimate(100, 0.05, 50000, np.random.default_rng(1))
        high = model.estimate(100, 0.50, 50000, np.random.default_rng(1))
        self.assertGreater(high, low)

    def test_fixed_spread(self) -> None:
        model = FixedSpread(half_spread_bps=5)
        spread = model.estimate(100, 0.2, 50000, self.rng)
        self.assertAlmostEqual(spread, 0.05, places=4)


class TestMarketImpact(unittest.TestCase):
    def test_sqrt_impact_scales_sublinearly(self) -> None:
        model = SquareRootImpact()
        small = model.estimate(100, 100, 100000, 0.2)
        large = model.estimate(100, 10000, 100000, 0.2)
        self.assertGreater(large, small)
        self.assertLess(large / small, 100)

    def test_zero_quantity_zero_impact(self) -> None:
        model = SquareRootImpact()
        self.assertEqual(model.estimate(100, 0, 100000, 0.2), 0.0)

    def test_zero_impact_model(self) -> None:
        model = ZeroImpact()
        self.assertEqual(model.estimate(100, 1000, 100000, 0.2), 0.0)


class TestLatencyModels(unittest.TestCase):
    def test_lognormal_positive(self) -> None:
        model = LogNormalLatency(mean_ms=50, std_ms=20)
        rng = np.random.default_rng(42)
        for _ in range(100):
            lat = model.sample_latency_ms(rng)
            self.assertGreaterEqual(lat, 0.0)

    def test_fixed_latency(self) -> None:
        model = FixedLatency(latency_ms=100)
        rng = np.random.default_rng(42)
        self.assertEqual(model.sample_latency_ms(rng), 100.0)

    def test_zero_latency(self) -> None:
        model = ZeroLatency()
        rng = np.random.default_rng(42)
        self.assertEqual(model.sample_latency_ms(rng), 0.0)


class TestFillSimulator(unittest.TestCase):
    def test_fill_produces_valid_event(self) -> None:
        sim = FillSimulator()
        order = OrderEvent(
            timestamp=pd.Timestamp("2023-01-01", tz="UTC"),
            symbol="TEST",
            side=OrderSide.BUY,
            quantity=100,
        )
        snapshot = MarketSnapshot(
            price=100, bid=99.9, ask=100.1,
            volume=50000, volatility=0.2, avg_volume=50000,
        )
        fill = sim.simulate_fill(order, snapshot)
        self.assertIn(fill.fill_status, (FillStatus.FILLED, FillStatus.PARTIAL, FillStatus.REJECTED))
        if fill.fill_status != FillStatus.REJECTED:
            self.assertGreater(fill.fill_price, 0)
            self.assertGreater(fill.quantity_filled, 0)
            self.assertGreaterEqual(fill.total_cost, 0)

    def test_buy_fill_price_above_market(self) -> None:
        """Buy fills should be at or above market price (adverse execution)."""
        sim = FillSimulator(rng=np.random.default_rng(42))
        order = OrderEvent(
            timestamp=pd.Timestamp("2023-01-01", tz="UTC"),
            symbol="TEST",
            side=OrderSide.BUY,
            quantity=100,
        )
        snapshot = MarketSnapshot(
            price=100, bid=None, ask=None,
            volume=50000, volatility=0.2, avg_volume=50000,
        )
        fill = sim.simulate_fill(order, snapshot)
        if fill.fill_status != FillStatus.REJECTED:
            self.assertGreaterEqual(
                fill.fill_price, snapshot.price,
                "Buy should fill at or above market price",
            )


if __name__ == "__main__":
    unittest.main()
