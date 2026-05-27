"""
Tests for the portfolio engine.

Validates:
- Position tracking correctness
- Realized/unrealized PnL separation
- Leverage constraint enforcement
- Turnover tracking
- Exposure calculations
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from backtesting.portfolio.portfolio_state import PortfolioState, Position
from backtesting.portfolio.exposure_engine import ExposureEngine
from backtesting.portfolio.leverage_constraints import LeverageConstraints
from backtesting.portfolio.position_sizing import (
    VolatilityTargetSizer,
    EqualWeightSizer,
    KellySizer,
)
from backtesting.portfolio.turnover_engine import TurnoverEngine
from backtesting.portfolio.pnl_engine import PnLEngine


class TestPosition(unittest.TestCase):
    def test_open_long(self) -> None:
        pos = Position(symbol="A")
        pos.apply_fill(100, 50.0)
        self.assertEqual(pos.quantity, 100)
        self.assertEqual(pos.avg_cost, 50.0)

    def test_close_long_realized_pnl(self) -> None:
        pos = Position(symbol="A")
        pos.apply_fill(100, 50.0)
        pos.market_price = 55.0
        realized = pos.apply_fill(-100, 55.0)
        self.assertAlmostEqual(realized, 500.0)
        self.assertTrue(pos.is_flat)

    def test_partial_close(self) -> None:
        pos = Position(symbol="A")
        pos.apply_fill(100, 50.0)
        realized = pos.apply_fill(-50, 60.0)
        self.assertAlmostEqual(realized, 500.0)
        self.assertEqual(pos.quantity, 50)
        self.assertEqual(pos.avg_cost, 50.0)

    def test_short_position(self) -> None:
        pos = Position(symbol="A")
        pos.apply_fill(-100, 50.0)
        self.assertTrue(pos.is_short)
        self.assertEqual(pos.quantity, -100)

    def test_short_close_pnl(self) -> None:
        pos = Position(symbol="A")
        pos.apply_fill(-100, 50.0)
        realized = pos.apply_fill(100, 45.0)
        self.assertAlmostEqual(realized, 500.0)

    def test_reverse_position(self) -> None:
        pos = Position(symbol="A")
        pos.apply_fill(100, 50.0)
        realized = pos.apply_fill(-150, 55.0)
        self.assertAlmostEqual(realized, 500.0)
        self.assertEqual(pos.quantity, -50)
        self.assertEqual(pos.avg_cost, 55.0)

    def test_unrealized_pnl(self) -> None:
        pos = Position(symbol="A", quantity=100, avg_cost=50.0, market_price=60.0)
        self.assertAlmostEqual(pos.unrealized_pnl, 1000.0)

    def test_unrealized_pnl_short(self) -> None:
        pos = Position(symbol="A", quantity=-100, avg_cost=50.0, market_price=45.0)
        self.assertAlmostEqual(pos.unrealized_pnl, 500.0)


class TestPortfolioState(unittest.TestCase):
    def test_initial_state(self) -> None:
        state = PortfolioState(1_000_000)
        self.assertEqual(state.cash, 1_000_000)
        self.assertEqual(state.portfolio_value, 1_000_000)
        self.assertEqual(state.gross_exposure, 0)

    def test_apply_fill_updates_cash(self) -> None:
        state = PortfolioState(1_000_000)
        state.apply_fill("A", 100, 50.0, costs=10.0)
        self.assertAlmostEqual(state.cash, 1_000_000 - 100 * 50 - 10)

    def test_portfolio_value_with_positions(self) -> None:
        state = PortfolioState(1_000_000)
        state.apply_fill("A", 100, 50.0, costs=0)
        state.update_prices({"A": 60.0})
        expected = (1_000_000 - 5000) + 100 * 60
        self.assertAlmostEqual(state.portfolio_value, expected)

    def test_leverage_calculation(self) -> None:
        state = PortfolioState(100_000)
        state.apply_fill("A", 1000, 50.0, costs=0)
        state.update_prices({"A": 50.0})
        self.assertAlmostEqual(state.gross_leverage, 0.5)

    def test_long_short_exposure(self) -> None:
        state = PortfolioState(100_000)
        state.apply_fill("A", 100, 50.0, costs=0)
        state.apply_fill("B", -50, 40.0, costs=0)
        state.update_prices({"A": 50.0, "B": 40.0})
        self.assertAlmostEqual(state.long_value, 5000)
        self.assertAlmostEqual(state.short_value, 2000)

    def test_drawdown(self) -> None:
        state = PortfolioState(100_000)
        state.apply_fill("A", 100, 50.0, costs=0)
        state.update_prices({"A": 50.0})
        _ = state.drawdown
        state.update_prices({"A": 40.0})
        dd = state.drawdown
        self.assertLess(dd, 0)


class TestLeverageConstraints(unittest.TestCase):
    def test_leverage_limit_scales_order(self) -> None:
        constraints = LeverageConstraints(max_gross_leverage=0.5)
        state = PortfolioState(100_000)
        state.apply_fill("A", 400, 100.0, costs=0)
        state.update_prices({"A": 100.0})

        scaled = constraints.scale_order(state, "B", 200, 100.0)
        self.assertLessEqual(
            abs(scaled * 100) + state.gross_exposure,
            0.5 * state.portfolio_value + 1,
        )

    def test_position_weight_limit(self) -> None:
        constraints = LeverageConstraints(max_position_weight=0.10)
        state = PortfolioState(100_000)

        scaled = constraints.scale_order(state, "A", 200, 100.0)
        self.assertLessEqual(abs(scaled * 100), 10_000 + 1)


class TestExposureEngine(unittest.TestCase):
    def test_exposure_snapshot(self) -> None:
        state = PortfolioState(100_000)
        state.apply_fill("A", 100, 50.0, costs=0)
        state.apply_fill("B", -50, 40.0, costs=0)
        state.update_prices({"A": 50.0, "B": 40.0})

        engine = ExposureEngine()
        snap = engine.compute(state)
        self.assertEqual(snap.long_count, 1)
        self.assertEqual(snap.short_count, 1)
        self.assertGreater(snap.gross_exposure, 0)


class TestPositionSizing(unittest.TestCase):
    def test_vol_target_sizer(self) -> None:
        sizer = VolatilityTargetSizer(target_volatility=0.15, max_weight=0.20)
        size = sizer.size(
            alpha_score=0.5, confidence=0.8,
            price=100, volatility=0.2,
            portfolio_value=1_000_000, current_position=0,
        )
        self.assertNotEqual(size, 0)
        self.assertLessEqual(abs(size * 100), 200_000 + 1)

    def test_zero_alpha_zero_position(self) -> None:
        sizer = VolatilityTargetSizer()
        size = sizer.size(
            alpha_score=0.0, confidence=0.8,
            price=100, volatility=0.2,
            portfolio_value=1_000_000, current_position=0,
        )
        self.assertEqual(size, 0)


class TestTurnoverEngine(unittest.TestCase):
    def test_turnover_tracking(self) -> None:
        engine = TurnoverEngine()
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        engine.record_trade(ts, 50000)
        engine.record_trade(ts, 30000)
        self.assertAlmostEqual(engine.daily_turnover(ts, 1_000_000), 0.08)

    def test_turnover_gate(self) -> None:
        engine = TurnoverEngine()
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        engine.record_trade(ts, 400_000)
        self.assertFalse(
            engine.can_trade(ts, 200_000, 1_000_000, max_daily_turnover=0.5)
        )


class TestPnLEngine(unittest.TestCase):
    def test_pnl_records(self) -> None:
        pnl = PnLEngine()
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        pnl.record(
            timestamp=ts, portfolio_value=1_000_000, cash=500_000,
            realized_pnl=1000, unrealized_pnl=500,
            slippage_cost=50, spread_cost=30,
        )
        df = pnl.to_dataframe()
        self.assertEqual(len(df), 1)
        self.assertIn("net_pnl", df.columns)


if __name__ == "__main__":
    unittest.main()
