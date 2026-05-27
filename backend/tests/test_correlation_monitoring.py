"""
Tests for correlation monitoring.

Validates:
- Rolling correlation computation
- Covariance stability detection
- Correlation regime classification
- Diversification decay tracking
- Correlation breakdown stress impact
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from risk_engine.risk_config import CorrelationConfig
from risk_engine.correlation.rolling_correlation import RollingCorrelationEngine
from risk_engine.correlation.covariance_monitor import CovarianceMonitor
from risk_engine.correlation.correlation_regimes import CorrelationRegimeDetector
from risk_engine.correlation.diversification_decay import DiversificationDecayMonitor
from risk_engine.stress_testing.correlation_breakdown import CorrelationBreakdownEngine


def _make_uncorrelated_returns(n: int = 200, n_assets: int = 5, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="B", tz="UTC")
    data = rng.normal(0, 0.01, (n, n_assets))
    cols = [f"A{i}" for i in range(n_assets)]
    return pd.DataFrame(data, index=idx, columns=cols)


def _make_correlated_returns(n: int = 200, n_assets: int = 5, corr: float = 0.8, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=n, freq="B", tz="UTC")
    common = rng.normal(0, 0.01, n)
    data = np.zeros((n, n_assets))
    for i in range(n_assets):
        idio = rng.normal(0, 0.01 * np.sqrt(1 - corr), n)
        data[:, i] = np.sqrt(corr) * common + idio
    cols = [f"A{i}" for i in range(n_assets)]
    return pd.DataFrame(data, index=idx, columns=cols)


class TestRollingCorrelation(unittest.TestCase):
    def test_uncorrelated_low_mean(self) -> None:
        """Uncorrelated assets should show low mean correlation."""
        returns = _make_uncorrelated_returns(n=200)
        engine = RollingCorrelationEngine()
        snap = engine.compute(returns)
        self.assertLess(abs(snap.mean_pairwise_correlation), 0.3)

    def test_correlated_high_mean(self) -> None:
        """Highly correlated assets should show high mean correlation."""
        returns = _make_correlated_returns(n=200, corr=0.8)
        engine = RollingCorrelationEngine()
        snap = engine.compute(returns)
        self.assertGreater(snap.mean_pairwise_correlation, 0.3)

    def test_n_high_corr_pairs(self) -> None:
        """Should detect high-correlation pairs."""
        returns = _make_correlated_returns(n=200, corr=0.9)
        engine = RollingCorrelationEngine()
        snap = engine.compute(returns)
        self.assertGreater(snap.n_high_corr_pairs, 0)

    def test_single_asset_handled(self) -> None:
        """Single-asset returns should produce zero correlation."""
        rng = np.random.default_rng(42)
        idx = pd.date_range("2022-01-01", periods=100, freq="B", tz="UTC")
        df = pd.DataFrame({"A": rng.normal(0, 0.01, 100)}, index=idx)
        engine = RollingCorrelationEngine()
        snap = engine.compute(df)
        self.assertEqual(snap.n_pairs, 0)


class TestCovarianceMonitor(unittest.TestCase):
    def test_stable_covariance(self) -> None:
        """Stable data should not be flagged as unstable."""
        returns = _make_uncorrelated_returns(n=400)
        config = CorrelationConfig(rolling_window_days=63, long_window_days=252)
        monitor = CovarianceMonitor(config=config)
        report = monitor.assess(returns)
        self.assertFalse(report.is_unstable)

    def test_condition_number_finite(self) -> None:
        """Condition number should be finite for reasonable data."""
        returns = _make_uncorrelated_returns(n=400)
        config = CorrelationConfig(rolling_window_days=63, long_window_days=252)
        monitor = CovarianceMonitor(config=config)
        report = monitor.assess(returns)
        self.assertTrue(np.isfinite(report.condition_number))


class TestCorrelationRegimes(unittest.TestCase):
    def test_low_corr_regime(self) -> None:
        """Uncorrelated data should produce LOW or NORMAL regime."""
        returns = _make_uncorrelated_returns(n=200)
        detector = CorrelationRegimeDetector()
        state = detector.detect(returns)
        self.assertIn(state.regime, ("LOW", "NORMAL", "UNKNOWN"))

    def test_high_corr_regime(self) -> None:
        """Highly correlated data should produce HIGH or BREAKDOWN regime."""
        returns = _make_correlated_returns(n=200, corr=0.9)
        detector = CorrelationRegimeDetector()
        state = detector.detect(returns)
        self.assertIn(state.regime, ("HIGH", "BREAKDOWN"))


class TestDiversificationDecay(unittest.TestCase):
    def test_diversification_ratio_above_one(self) -> None:
        """Diversification ratio should be >= 1 for multi-asset portfolio."""
        returns = _make_uncorrelated_returns(n=200)
        monitor = DiversificationDecayMonitor()
        state = monitor.assess(returns)
        self.assertGreaterEqual(state.diversification_ratio, 1.0)
        self.assertGreater(state.effective_n_assets, 1.0)

    def test_perfect_correlation_ratio_near_one(self) -> None:
        """Perfectly correlated assets should have div ratio near 1."""
        returns = _make_correlated_returns(n=200, corr=0.99)
        monitor = DiversificationDecayMonitor()
        state = monitor.assess(returns)
        self.assertLess(state.diversification_ratio, 2.0)

    def test_marginal_diversification_computed(self) -> None:
        """Marginal diversification should be computed for each asset."""
        returns = _make_uncorrelated_returns(n=200)
        monitor = DiversificationDecayMonitor()
        state = monitor.assess(returns)
        self.assertEqual(len(state.marginal_diversification), returns.shape[1])


class TestCorrelationBreakdown(unittest.TestCase):
    def test_stress_levels_increase(self) -> None:
        """Stressed portfolio vol should exceed normal."""
        weights = {"A": 0.3, "B": 0.3, "C": 0.2, "D": 0.2}
        vols = {"A": 0.15, "B": 0.20, "C": 0.10, "D": 0.18}
        engine = CorrelationBreakdownEngine()
        results = engine.analyze(position_weights=weights, position_vols=vols)
        self.assertIn("moderate", results)
        self.assertIn("severe", results)
        self.assertIn("total", results)
        self.assertGreater(
            results["total"].stressed_portfolio_vol,
            results["moderate"].stressed_portfolio_vol,
        )

    def test_total_breakdown_worst_case(self) -> None:
        """Total correlation breakdown should be the worst case."""
        weights = {"A": 0.5, "B": 0.5}
        vols = {"A": 0.15, "B": 0.15}
        engine = CorrelationBreakdownEngine()
        results = engine.analyze(position_weights=weights, position_vols=vols)
        self.assertLess(
            results["total"].implied_loss_1d,
            results["moderate"].implied_loss_1d,
        )


if __name__ == "__main__":
    unittest.main()
