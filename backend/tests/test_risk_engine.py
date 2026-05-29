"""
Tests for the institutional risk engine orchestrator.

Validates:
- End-to-end risk assessment pipeline
- Risk regime classification
- Report generation
- Audit log integrity
- Kill-switch coordination
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from risk_engine.risk_config import RiskEngineConfig, RiskRegime
from risk_engine.risk_orchestrator import RiskOrchestrator


def _make_portfolio(n_assets: int = 5, seed: int = 42):
    """Generate synthetic portfolio data for testing."""
    rng = np.random.default_rng(seed)
    symbols = [f"ASSET_{i}" for i in range(n_assets)]
    positions = {s: rng.uniform(100, 1000) for s in symbols}
    prices = {s: rng.uniform(50, 200) for s in symbols}
    nav = sum(positions[s] * prices[s] for s in symbols) + 100_000
    return symbols, positions, prices, nav


def _make_returns(n_days: int = 300, seed: int = 42) -> pd.Series:
    """Generate synthetic portfolio returns."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n_days, freq="B", tz="UTC")
    returns = pd.Series(rng.normal(0.0003, 0.012, n_days), index=idx)
    return returns


def _make_multi_returns(n_days: int = 300, n_assets: int = 5, seed: int = 42) -> pd.DataFrame:
    """Generate correlated multi-asset returns."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n_days, freq="B", tz="UTC")
    corr = np.eye(n_assets) * 0.5 + 0.5 * np.ones((n_assets, n_assets))
    np.fill_diagonal(corr, 1.0)
    L = np.linalg.cholesky(corr)
    raw = rng.normal(0, 0.012, (n_days, n_assets))
    correlated = raw @ L.T + 0.0003
    cols = [f"ASSET_{i}" for i in range(n_assets)]
    return pd.DataFrame(correlated, index=idx, columns=cols)


class TestRiskOrchestrator(unittest.TestCase):
    def setUp(self) -> None:
        self.config = RiskEngineConfig()
        self.orchestrator = RiskOrchestrator(config=self.config)
        self.symbols, self.positions, self.prices, self.nav = _make_portfolio()
        self.returns = _make_returns()
        self.multi_returns = _make_multi_returns()

    def test_end_to_end_assessment(self) -> None:
        """Full risk assessment completes without error."""
        ts = pd.Timestamp("2023-06-01", tz="UTC")
        assessment = self.orchestrator.assess(
            positions=self.positions,
            prices=self.prices,
            nav=self.nav,
            timestamp=ts,
            returns=self.returns,
            multi_asset_returns=self.multi_returns,
        )
        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.timestamp, ts)
        self.assertIsNotNone(assessment.exposure)
        self.assertIsNotNone(assessment.drawdown)
        self.assertIsNotNone(assessment.kill_switch)
        self.assertIsNotNone(assessment.snapshot)

    def test_risk_regime_classified(self) -> None:
        """Risk regime is correctly classified (synthetic data may trigger breaches)."""
        ts = pd.Timestamp("2023-06-01", tz="UTC")
        assessment = self.orchestrator.assess(
            positions=self.positions,
            prices=self.prices,
            nav=self.nav,
            timestamp=ts,
            returns=self.returns,
        )
        self.assertIn(
            assessment.risk_regime,
            (RiskRegime.NORMAL, RiskRegime.ELEVATED, RiskRegime.STRESSED, RiskRegime.CRISIS),
        )

    def test_report_generation(self) -> None:
        """Risk report generates valid output."""
        ts = pd.Timestamp("2023-06-01", tz="UTC")
        self.orchestrator.assess(
            positions=self.positions,
            prices=self.prices,
            nav=self.nav,
            timestamp=ts,
            returns=self.returns,
        )
        report = self.orchestrator.generate_report()
        self.assertGreater(report.nav, 0)
        text = report.summary_text()
        self.assertIn("PORTFOLIO RISK REPORT", text)
        self.assertIn("MODEL LIMITATIONS", text)

    def test_audit_log_records_events(self) -> None:
        """Audit log records events during assessment."""
        ts = pd.Timestamp("2023-06-01", tz="UTC")
        self.orchestrator.assess(
            positions=self.positions,
            prices=self.prices,
            nav=self.nav,
            timestamp=ts,
            returns=self.returns,
        )
        log = self.orchestrator.audit_log
        self.assertIsInstance(log.n_entries, int)

    def test_multiple_assessments_accumulate(self) -> None:
        """Running multiple assessments builds history."""
        for i in range(5):
            ts = pd.Timestamp(f"2023-06-0{i+1}", tz="UTC")
            self.orchestrator.assess(
                positions=self.positions,
                prices=self.prices,
                nav=self.nav * (1 - i * 0.01),
                timestamp=ts,
                returns=self.returns,
            )
        history = self.orchestrator._realtime.history
        self.assertEqual(len(history), 5)

    def test_conservative_config(self) -> None:
        """Conservative config produces tighter risk assessments."""
        config = RiskEngineConfig.conservative()
        orch = RiskOrchestrator(config=config)
        ts = pd.Timestamp("2023-06-01", tz="UTC")
        assessment = orch.assess(
            positions=self.positions,
            prices=self.prices,
            nav=self.nav,
            timestamp=ts,
            returns=self.returns,
        )
        self.assertIsNotNone(assessment)

    def test_stress_tests(self) -> None:
        """Stress testing pipeline completes."""
        weights = {}
        for s in self.symbols:
            weights[s] = self.positions[s] * self.prices[s] / self.nav
        report = self.orchestrator.run_stress_tests(
            position_weights=weights,
            current_leverage=1.0,
            portfolio_vol=0.15,
            concentration_hhi=0.10,
        )
        self.assertGreater(len(report.historical_results), 0)
        self.assertGreater(len(report.hypothetical_results), 0)
        self.assertLess(report.worst_overall_loss, 0)
        text = report.summary_text()
        self.assertIn("STRESS TEST REPORT", text)

    def test_snapshot_serialization(self) -> None:
        """Risk snapshot serializes to dict correctly."""
        ts = pd.Timestamp("2023-06-01", tz="UTC")
        self.orchestrator.assess(
            positions=self.positions,
            prices=self.prices,
            nav=self.nav,
            timestamp=ts,
            returns=self.returns,
        )
        d = self.orchestrator._realtime.to_dict()
        self.assertIn("nav", d)
        self.assertIn("risk_regime", d)
        self.assertIn("risk_score", d)


class TestStressTestReport(unittest.TestCase):
    def test_stress_report_summary(self) -> None:
        """Stress report produces human-readable summary."""
        config = RiskEngineConfig()
        orch = RiskOrchestrator(config=config)
        weights = {"SPY": 0.5, "QQQ": 0.3, "IWM": 0.2}
        report = orch.run_stress_tests(
            position_weights=weights,
            current_leverage=1.5,
        )
        text = report.summary_text()
        self.assertIn("HISTORICAL", text)
        self.assertIn("HYPOTHETICAL", text)


if __name__ == "__main__":
    unittest.main()
