"""
Tests for drawdown monitoring and kill-switch controls.

Validates:
- Drawdown calculation correctness
- Stage classification
- Kill-switch activation and recovery
- Capital preservation logic
- Recovery monitor tracking
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from risk_engine.risk_config import DrawdownConfig, RiskRegime
from risk_engine.drawdown.drawdown_monitor import DrawdownMonitor
from risk_engine.drawdown.kill_switch import KillSwitch, KillSwitchState
from risk_engine.drawdown.capital_preservation import CapitalPreservationEngine
from risk_engine.drawdown.recovery_monitor import RecoveryMonitor


class TestDrawdownMonitor(unittest.TestCase):
    def setUp(self) -> None:
        self.config = DrawdownConfig(
            warning_threshold=-0.05,
            reduce_threshold=-0.10,
            critical_threshold=-0.15,
            kill_switch_threshold=-0.20,
        )
        self.monitor = DrawdownMonitor(config=self.config)

    def test_no_drawdown_at_start(self) -> None:
        """First update establishes HWM, no drawdown."""
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        state = self.monitor.update(ts, 1_000_000)
        self.assertEqual(state.current_drawdown, 0.0)
        self.assertEqual(state.drawdown_stage, "NORMAL")

    def test_drawdown_calculation(self) -> None:
        """Drawdown correctly computes from high water mark."""
        ts1 = pd.Timestamp("2023-01-01", tz="UTC")
        ts2 = pd.Timestamp("2023-01-02", tz="UTC")
        self.monitor.update(ts1, 1_000_000)
        state = self.monitor.update(ts2, 900_000)
        self.assertAlmostEqual(state.current_drawdown, -0.10, places=2)

    def test_hwm_updates_on_new_high(self) -> None:
        """HWM moves up when portfolio hits new high."""
        ts1 = pd.Timestamp("2023-01-01", tz="UTC")
        ts2 = pd.Timestamp("2023-01-02", tz="UTC")
        ts3 = pd.Timestamp("2023-01-03", tz="UTC")
        self.monitor.update(ts1, 1_000_000)
        self.monitor.update(ts2, 1_100_000)
        state = self.monitor.update(ts3, 1_050_000)
        self.assertAlmostEqual(state.high_water_mark, 1_100_000)
        self.assertAlmostEqual(
            state.current_drawdown,
            (1_050_000 - 1_100_000) / 1_100_000,
            places=4,
        )

    def test_stage_classification(self) -> None:
        """Drawdown stages match configured thresholds."""
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        self.monitor.update(ts, 1_000_000)

        ts2 = pd.Timestamp("2023-01-02", tz="UTC")
        state = self.monitor.update(ts2, 940_000)
        self.assertEqual(state.drawdown_stage, "WARNING")

        ts3 = pd.Timestamp("2023-01-03", tz="UTC")
        state = self.monitor.update(ts3, 880_000)
        self.assertEqual(state.drawdown_stage, "REDUCE")

        ts4 = pd.Timestamp("2023-01-04", tz="UTC")
        state = self.monitor.update(ts4, 840_000)
        self.assertEqual(state.drawdown_stage, "CRITICAL")

        ts5 = pd.Timestamp("2023-01-05", tz="UTC")
        state = self.monitor.update(ts5, 790_000)
        self.assertEqual(state.drawdown_stage, "KILL")

    def test_recovery_resets_stage(self) -> None:
        """Full recovery returns to NORMAL stage."""
        ts1 = pd.Timestamp("2023-01-01", tz="UTC")
        ts2 = pd.Timestamp("2023-01-02", tz="UTC")
        ts3 = pd.Timestamp("2023-01-03", tz="UTC")
        self.monitor.update(ts1, 1_000_000)
        self.monitor.update(ts2, 900_000)
        state = self.monitor.update(ts3, 1_000_000)
        self.assertEqual(state.drawdown_stage, "NORMAL")


class TestKillSwitch(unittest.TestCase):
    def setUp(self) -> None:
        self.config = DrawdownConfig(
            kill_switch_threshold=-0.20,
            critical_threshold=-0.15,
            reduce_threshold=-0.10,
            warning_threshold=-0.05,
            recovery_buffer_pct=0.02,
            min_recovery_days=5,
        )
        self.ks = KillSwitch(config=self.config)

    def test_normal_operation(self) -> None:
        """No drawdown → ACTIVE state."""
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        action = self.ks.evaluate(
            current_drawdown=-0.02,
            drawdown_speed=0.0,
            timestamp=ts,
        )
        self.assertEqual(action.state, KillSwitchState.ACTIVE)
        self.assertTrue(action.allow_new_trades)
        self.assertEqual(action.leverage_multiplier, 1.0)

    def test_kill_switch_activates(self) -> None:
        """Deep drawdown activates kill-switch."""
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        action = self.ks.evaluate(
            current_drawdown=-0.22,
            drawdown_speed=-0.03,
            timestamp=ts,
        )
        self.assertEqual(action.state, KillSwitchState.HALTED)
        self.assertFalse(action.allow_new_trades)
        self.assertEqual(action.leverage_multiplier, 0.0)

    def test_kill_switch_stays_halted(self) -> None:
        """Kill switch remains halted until recovery conditions met."""
        ts1 = pd.Timestamp("2023-01-01", tz="UTC")
        self.ks.evaluate(current_drawdown=-0.22, drawdown_speed=-0.03, timestamp=ts1)

        ts2 = pd.Timestamp("2023-01-02", tz="UTC")
        action = self.ks.evaluate(current_drawdown=-0.21, drawdown_speed=0.0, timestamp=ts2)
        self.assertEqual(action.state, KillSwitchState.HALTED)

    def test_reducing_state(self) -> None:
        """Moderate drawdown triggers REDUCING state."""
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        action = self.ks.evaluate(
            current_drawdown=-0.12,
            drawdown_speed=-0.01,
            timestamp=ts,
        )
        self.assertEqual(action.state, KillSwitchState.REDUCING)
        self.assertFalse(action.allow_position_increases)

    def test_worst_strategies_disabled(self) -> None:
        """Critical drawdown disables worst-performing strategies."""
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        strategy_pnls = {"mom": -5000, "mean_rev": 2000, "trend": -8000}
        action = self.ks.evaluate(
            current_drawdown=-0.17,
            drawdown_speed=-0.02,
            timestamp=ts,
            strategy_pnls=strategy_pnls,
        )
        self.assertEqual(action.state, KillSwitchState.REDUCING)
        self.assertIn("trend", action.disabled_strategies)


class TestCapitalPreservation(unittest.TestCase):
    def test_full_budget_at_no_drawdown(self) -> None:
        """With no drawdown, full risk budget is available."""
        engine = CapitalPreservationEngine()
        state = engine.assess(current_drawdown=0.0, realized_vol=0.15)
        self.assertEqual(state.preservation_score, 1.0)
        self.assertEqual(state.remaining_risk_budget, 0.25)

    def test_budget_shrinks_with_drawdown(self) -> None:
        """Risk budget decreases as drawdown deepens."""
        engine = CapitalPreservationEngine()
        state_0 = engine.assess(current_drawdown=0.0, realized_vol=0.15)
        state_10 = engine.assess(current_drawdown=-0.10, realized_vol=0.15)
        self.assertGreater(
            state_0.remaining_risk_budget,
            state_10.remaining_risk_budget,
        )
        self.assertGreater(
            state_0.preservation_score,
            state_10.preservation_score,
        )

    def test_zero_budget_at_max_loss(self) -> None:
        """At max acceptable loss, budget is zero."""
        engine = CapitalPreservationEngine(max_acceptable_total_loss=0.25)
        state = engine.assess(current_drawdown=-0.25, realized_vol=0.15)
        self.assertEqual(state.remaining_risk_budget, 0.0)

    def test_recovery_computation(self) -> None:
        """Recovery required increases non-linearly with drawdown."""
        engine = CapitalPreservationEngine()
        state_10 = engine.assess(current_drawdown=-0.10, realized_vol=0.15)
        state_30 = engine.assess(current_drawdown=-0.30, realized_vol=0.15)
        self.assertGreater(state_30.recovery_required, state_10.recovery_required)


class TestRecoveryMonitor(unittest.TestCase):
    def test_not_recovering_initially(self) -> None:
        """No recovery when no drawdown occurred."""
        monitor = RecoveryMonitor()
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        state = monitor.update(current_drawdown=0.0, timestamp=ts)
        self.assertFalse(state.is_recovering)

    def test_recovery_detection(self) -> None:
        """Recovery detected after drawdown bounces."""
        config = DrawdownConfig(reduce_threshold=-0.10, recovery_buffer_pct=0.02)
        monitor = RecoveryMonitor(config=config)

        ts1 = pd.Timestamp("2023-01-01", tz="UTC")
        monitor.update(current_drawdown=-0.12, timestamp=ts1)

        ts2 = pd.Timestamp("2023-01-05", tz="UTC")
        state = monitor.update(current_drawdown=-0.08, timestamp=ts2)
        self.assertTrue(state.is_recovering)
        self.assertGreater(state.recovery_pct, 0)


if __name__ == "__main__":
    unittest.main()
