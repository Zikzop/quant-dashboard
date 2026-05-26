"""
Unit tests for Phase 3 institutional research engine (no network).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from alpha_validation.alpha_decay import analyze_alpha_decay
from alpha_validation.bootstrap_validation import run_bootstrap_validation
from alpha_validation.feature_stability import analyze_feature_stability
from alpha_validation.rolling_validation import RollingValidationConfig, run_rolling_validation
from experiments.experiment_tracker import ExperimentTracker, ExperimentTrackerConfig
from feature_analysis.feature_importance import analyze_feature_importance
from feature_analysis.mutual_information import compute_mutual_information
from feature_analysis.regime_feature_analysis import analyze_regime_features
from loaders.dataset_loader import DatasetLoader, DatasetLoaderConfig, DatasetTier
from pipelines.feature_pipeline import FeaturePipeline
from pipelines.normalization_pipeline import NormalizationPipeline
from statistical_testing.autocorrelation_tests import run_autocorrelation_diagnostics
from statistical_testing.distribution_tests import run_distribution_diagnostics
from statistical_testing.hypothesis_tests import bootstrap_significance, run_ttest
from statistical_testing.stationarity_tests import run_stationarity_suite
from storage.parquet_handler import ParquetHandler


def _normalized_frame(n: int = 120) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    open_ = close + rng.normal(0, 0.1, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.5, n)
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.integers(100, 1000, n).astype(float),
        },
        index=idx,
    )


def _strategy_returns(n: int = 300) -> pd.Series:
    rng = np.random.default_rng(7)
    idx = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    returns = rng.normal(0.0003, 0.01, size=n)
    return pd.Series(returns, index=idx, name="strategy_return")


class TestDatasetLoader(unittest.TestCase):
    def test_load_features_tier(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            features_dir = Path(tmp) / "features"
            handler = ParquetHandler(features_dir)
            norm = _normalized_frame(40)
            feat = FeaturePipeline().run(norm)
            exported = NormalizationPipeline().to_timestamp_column(feat)
            handler.save(exported, "TEST", "1d", index=False)

            loader = DatasetLoader(
                DatasetLoaderConfig(tier=DatasetTier.FEATURES),
                paths=type(
                    "P",
                    (),
                    {
                        "raw": Path(tmp) / "raw",
                        "clean": Path(tmp) / "clean",
                        "normalized": Path(tmp) / "normalized",
                        "features": features_dir,
                        "root": Path(tmp),
                    },
                )(),
            )
            df = loader.load("TEST", "1d")
            self.assertEqual(str(df.index.tz), "UTC")
            self.assertIn("log_return", df.columns)
            self.assertIn("close", df.columns)

    def test_date_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            clean_dir = Path(tmp) / "clean"
            handler = ParquetHandler(clean_dir)
            norm = _normalized_frame(30)
            exported = NormalizationPipeline().to_timestamp_column(norm)
            handler.save(exported, "TEST", "1d", index=False)

            loader = DatasetLoader(
                DatasetLoaderConfig(tier=DatasetTier.CLEAN),
                paths=type(
                    "P",
                    (),
                    {
                        "raw": Path(tmp) / "raw",
                        "clean": clean_dir,
                        "normalized": Path(tmp) / "normalized",
                        "features": Path(tmp) / "features",
                        "root": Path(tmp),
                    },
                )(),
            )
            start = pd.Timestamp("2023-01-10", tz="UTC")
            end = pd.Timestamp("2023-01-20", tz="UTC")
            df = loader.load("TEST", "1d", start=start, end=end)
            self.assertTrue((df.index >= start).all())
            self.assertTrue((df.index <= end).all())


class TestStationarityTests(unittest.TestCase):
    def test_stationarity_suite_structure(self) -> None:
        returns = _normalized_frame(80)["close"].pct_change().dropna()
        result = run_stationarity_suite(returns)
        self.assertIsNotNone(result.adf)
        self.assertIsNotNone(result.kpss)
        self.assertIn(result.assessment, ("stationary", "non_stationary", "inconclusive"))
        self.assertTrue(len(result.summary) > 0)

    def test_hurst_exponent_bounded(self) -> None:
        from statistical_testing.stationarity_tests import estimate_hurst_exponent

        returns = _normalized_frame(100)["close"].pct_change().dropna()
        hurst = estimate_hurst_exponent(returns)
        if hurst.regime_hint != "insufficient_data":
            self.assertFalse(np.isnan(hurst.exponent))


class TestDistributionTests(unittest.TestCase):
    def test_fat_tail_detection(self) -> None:
        rng = np.random.default_rng(0)
        fat_tails = rng.standard_t(df=3, size=500)
        diag = run_distribution_diagnostics(pd.Series(fat_tails))
        self.assertIn(diag.tails.tail_assessment, ("fat", "extreme_fat", "normal", "thin"))
        self.assertIsNotNone(diag.jarque_bera.p_value)


class TestBootstrapValidation(unittest.TestCase):
    def test_bootstrap_robustness_output(self) -> None:
        returns = _strategy_returns(200)
        result = run_bootstrap_validation(returns)
        self.assertGreater(result.n_obs, 0)
        self.assertTrue(hasattr(result.sharpe, "ci_lower"))
        self.assertTrue(hasattr(result.expectancy, "is_robust"))


class TestRollingValidation(unittest.TestCase):
    def test_walk_forward_folds(self) -> None:
        returns = _strategy_returns(400)
        result = run_rolling_validation(
            returns,
            config=RollingValidationConfig(train_size=126, test_size=42, step_size=42),
        )
        self.assertGreater(len(result.folds), 0)
        self.assertIsInstance(result.mean_test_sharpe, float)


class TestAlphaDecay(unittest.TestCase):
    def test_rolling_metrics(self) -> None:
        returns = _strategy_returns(200)
        analysis = analyze_alpha_decay(returns)
        self.assertIn(
            analysis.decay_assessment,
            ("stable", "mild_decay", "severe_decay", "insufficient_data"),
        )


class TestFeatureImportance(unittest.TestCase):
    def test_mutual_information_ranking(self) -> None:
        n = 150
        rng = np.random.default_rng(1)
        X = pd.DataFrame({"f1": rng.normal(0, 1, n), "f2": rng.normal(0, 1, n)})
        y = X["f1"] * 0.5 + rng.normal(0, 0.1, n)
        report = compute_mutual_information(X, y)
        self.assertGreater(len(report.scores), 0)
        self.assertIn("causality", report.disclaimer.lower())

    def test_feature_importance_report(self) -> None:
        n = 120
        rng = np.random.default_rng(2)
        X = pd.DataFrame(
            {
                "feat_a": rng.normal(0, 1, n),
                "feat_b": rng.normal(0, 1, n),
            }
        )
        y = X["feat_a"] + rng.normal(0, 0.5, n)
        report = analyze_feature_importance(X, y, compute_rolling=False)
        self.assertGreater(len(report.permutation), 0)
        self.assertIn("causality", report.disclaimer.lower())


class TestFeatureStability(unittest.TestCase):
    def test_stability_report(self) -> None:
        n = 100
        rng = np.random.default_rng(3)
        X = pd.DataFrame({"x1": rng.normal(0, 1, n), "x2": rng.normal(0, 1, n)})
        y = X["x1"] * 0.3 + rng.normal(0, 1, n)
        report = analyze_feature_stability(X, y)
        self.assertGreater(len(report.features), 0)


class TestRegimeFeatureAnalysis(unittest.TestCase):
    def test_regime_profiles(self) -> None:
        n = 100
        rng = np.random.default_rng(4)
        X = pd.DataFrame({"feat": rng.normal(0, 1, n)})
        y = rng.normal(0, 1, n)
        regime = pd.Series(["A"] * 50 + ["B"] * 50)
        report = analyze_regime_features(X, y, regime)
        self.assertEqual(len(report.features), 1)
        self.assertGreater(len(report.features[0].regimes), 0)


class TestHypothesisTests(unittest.TestCase):
    def test_ttest_and_bootstrap(self) -> None:
        rng = np.random.default_rng(5)
        series = pd.Series(rng.normal(0.001, 0.01, 100))
        t_result = run_ttest(series, popmean=0.0)
        self.assertIsInstance(t_result.p_value, float)
        boot = bootstrap_significance(series, n_bootstrap=500, rng=rng)
        self.assertIsInstance(boot.p_value, float)


class TestAutocorrelation(unittest.TestCase):
    def test_diagnostics_suite(self) -> None:
        returns = _strategy_returns(150)
        diag = run_autocorrelation_diagnostics(returns, lags=5)
        self.assertTrue(len(diag.summary) > 0)


class TestExperimentTracker(unittest.TestCase):
    def test_create_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tracker = ExperimentTracker(
                ExperimentTrackerConfig(storage_dir=Path(tmp), auto_flush=True)
            )
            record = tracker.create_experiment(
                dataset_version="TEST_1d_v1",
                features_used=["log_return", "z_score"],
                parameters={"window": 20},
                metrics={"sharpe": 1.2},
                notes="unit test",
                tags=["test"],
            )
            loaded = tracker.get_by_id(record.experiment_id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.metrics["sharpe"], 1.2)

            log_path = Path(tmp) / "experiments.jsonl"
            self.assertTrue(log_path.exists())
            with log_path.open() as f:
                line = json.loads(f.readline())
            self.assertEqual(line["experiment_id"], record.experiment_id)


if __name__ == "__main__":
    unittest.main()
