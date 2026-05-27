"""
Tests for exposure monitoring.

Validates:
- Gross/net exposure computation
- Leverage monitoring
- Concentration analysis
- Factor exposure estimation
- Volatility-adjusted exposure
- Exposure assessment pipeline
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from risk_engine.risk_config import ExposureConfig, RiskRegime
from risk_engine.exposure.gross_net_exposure import GrossNetExposureEngine
from risk_engine.exposure.leverage_monitor import LeverageMonitor
from risk_engine.exposure.concentration_monitor import ConcentrationMonitor
from risk_engine.exposure.factor_exposure import FactorExposureEngine
from risk_engine.exposure.exposure_monitor import ExposureMonitor


class TestGrossNetExposure(unittest.TestCase):
    def test_long_only_exposure(self) -> None:
        """Long-only portfolio: gross == net."""
        engine = GrossNetExposureEngine()
        positions = {"A": 100, "B": 200}
        prices = {"A": 50.0, "B": 30.0}
        nav = 100 * 50 + 200 * 30 + 5000
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        snap = engine.compute(positions, prices, nav, ts)
        self.assertAlmostEqual(snap.gross_exposure, snap.net_exposure)
        self.assertEqual(snap.long_count, 2)
        self.assertEqual(snap.short_count, 0)

    def test_long_short_exposure(self) -> None:
        """Long-short portfolio: gross > net."""
        engine = GrossNetExposureEngine()
        positions = {"A": 100, "B": -50}
        prices = {"A": 100.0, "B": 100.0}
        nav = 100 * 100 - 50 * 100 + 10000
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        snap = engine.compute(positions, prices, nav, ts)
        self.assertGreater(snap.gross_exposure, abs(snap.net_exposure))
        self.assertEqual(snap.long_count, 1)
        self.assertEqual(snap.short_count, 1)

    def test_vol_adjusted_exposure(self) -> None:
        """Vol-adjusted exposure differs from raw when vol and sizes vary."""
        engine = GrossNetExposureEngine()
        positions = {"LOW_VOL": 300, "HIGH_VOL": 100}
        prices = {"LOW_VOL": 100.0, "HIGH_VOL": 100.0}
        nav = 300 * 100 + 100 * 100 + 10000
        volatilities = {"LOW_VOL": 0.10, "HIGH_VOL": 0.30}
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        snap = engine.compute(positions, prices, nav, ts, volatilities=volatilities)
        self.assertNotAlmostEqual(snap.vol_adjusted_gross, snap.gross_leverage)

    def test_zero_nav_raises(self) -> None:
        """Zero NAV should raise ValueError."""
        engine = GrossNetExposureEngine()
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        with self.assertRaises(ValueError):
            engine.compute({"A": 100}, {"A": 50.0}, 0.0, ts)

    def test_history_accumulates(self) -> None:
        """Multiple computations build history."""
        engine = GrossNetExposureEngine()
        for i in range(5):
            ts = pd.Timestamp(f"2023-01-0{i+1}", tz="UTC")
            engine.compute({"A": 100}, {"A": 50.0}, 10000.0, ts)
        self.assertEqual(len(engine.history()), 5)
        df = engine.to_dataframe()
        self.assertEqual(len(df), 5)


class TestLeverageMonitor(unittest.TestCase):
    def test_within_limits(self) -> None:
        """Portfolio within limits: no breach."""
        config = ExposureConfig(max_gross_leverage=2.0, max_net_exposure_ratio=1.0)
        monitor = LeverageMonitor(config=config)
        engine = GrossNetExposureEngine()
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        snap = engine.compute({"A": 100}, {"A": 50.0}, 10000.0, ts)
        status = monitor.check(snap)
        self.assertFalse(status.gross_breach)
        self.assertFalse(status.net_breach)
        self.assertGreater(status.headroom_gross, 0)

    def test_leverage_breach(self) -> None:
        """Excessive leverage triggers breach."""
        config = ExposureConfig(max_gross_leverage=0.3)
        monitor = LeverageMonitor(config=config)
        engine = GrossNetExposureEngine()
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        snap = engine.compute({"A": 100}, {"A": 50.0}, 5100.0, ts)
        status = monitor.check(snap)
        self.assertTrue(status.gross_breach)


class TestConcentrationMonitor(unittest.TestCase):
    def test_equal_weight_low_hhi(self) -> None:
        """Equal-weight portfolio should have low HHI."""
        monitor = ConcentrationMonitor()
        positions = {f"S{i}": 100 for i in range(10)}
        prices = {f"S{i}": 100.0 for i in range(10)}
        nav = 10 * 100 * 100 + 50000
        snap = monitor.compute(positions, prices, nav)
        self.assertLess(snap.hhi, 0.15)
        self.assertEqual(snap.n_positions, 10)
        self.assertGreater(snap.effective_n, 5)

    def test_concentrated_high_hhi(self) -> None:
        """Single-name concentrated portfolio has high HHI."""
        monitor = ConcentrationMonitor()
        positions = {"BIG": 900, "SMALL": 10}
        prices = {"BIG": 100.0, "SMALL": 100.0}
        nav = 900 * 100 + 10 * 100 + 1000
        snap = monitor.compute(positions, prices, nav)
        self.assertGreater(snap.hhi, 0.5)
        self.assertGreater(snap.max_single_name, 0.5)

    def test_sector_weights(self) -> None:
        """Sector weights computed correctly."""
        monitor = ConcentrationMonitor()
        positions = {"AAPL": 100, "MSFT": 100, "XOM": 100}
        prices = {"AAPL": 100.0, "MSFT": 100.0, "XOM": 100.0}
        nav = 300 * 100 + 10000
        sector_map = {"AAPL": "Tech", "MSFT": "Tech", "XOM": "Energy"}
        snap = monitor.compute(positions, prices, nav, sector_map=sector_map)
        self.assertIn("Tech", snap.sector_weights)
        self.assertIn("Energy", snap.sector_weights)
        self.assertGreater(snap.sector_weights["Tech"], snap.sector_weights["Energy"])

    def test_empty_portfolio(self) -> None:
        """Empty portfolio produces zero concentration."""
        monitor = ConcentrationMonitor()
        snap = monitor.compute({}, {}, 10000)
        self.assertEqual(snap.n_positions, 0)
        self.assertEqual(snap.hhi, 0.0)


class TestFactorExposure(unittest.TestCase):
    def test_market_beta_positive(self) -> None:
        """Portfolio correlated with market should show positive beta."""
        rng = np.random.default_rng(42)
        n = 200
        idx = pd.date_range("2022-01-01", periods=n, freq="B", tz="UTC")
        mkt = pd.Series(rng.normal(0.0005, 0.01, n), index=idx)
        port = 1.2 * mkt + pd.Series(rng.normal(0, 0.003, n), index=idx)

        engine = FactorExposureEngine(lookback_days=100)
        result = engine.estimate(port, mkt)
        self.assertGreater(result.market_beta, 0.5)
        self.assertGreater(result.r_squared, 0.3)

    def test_insufficient_data(self) -> None:
        """Handles insufficient data gracefully."""
        idx = pd.date_range("2022-01-01", periods=5, freq="B", tz="UTC")
        port = pd.Series([0.01, -0.01, 0.005, -0.005, 0.001], index=idx)
        mkt = pd.Series([0.01, -0.005, 0.003, -0.002, 0.001], index=idx)
        engine = FactorExposureEngine()
        result = engine.estimate(port, mkt)
        self.assertEqual(result.market_beta, 0.0)


class TestExposureMonitor(unittest.TestCase):
    def test_assessment_pipeline(self) -> None:
        """Full exposure assessment pipeline completes."""
        config = ExposureConfig()
        monitor = ExposureMonitor(config=config)
        positions = {"A": 100, "B": 200, "C": -50}
        prices = {"A": 50.0, "B": 30.0, "C": 80.0}
        nav = 100 * 50 + 200 * 30 - 50 * 80 + 20000
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        assessment = monitor.assess(positions, prices, nav, ts)
        self.assertIsNotNone(assessment.exposure)
        self.assertIsNotNone(assessment.leverage_status)
        self.assertIsNotNone(assessment.concentration)
        self.assertIsInstance(assessment.risk_regime, RiskRegime)

    def test_breach_detection(self) -> None:
        """Breaches detected when limits exceeded."""
        config = ExposureConfig(max_gross_leverage=0.5)
        monitor = ExposureMonitor(config=config)
        positions = {"A": 500}
        prices = {"A": 100.0}
        nav = 55000
        ts = pd.Timestamp("2023-01-01", tz="UTC")
        assessment = monitor.assess(positions, prices, nav, ts)
        self.assertTrue(assessment.requires_action)
        self.assertGreater(len(assessment.breaches), 0)


if __name__ == "__main__":
    unittest.main()
