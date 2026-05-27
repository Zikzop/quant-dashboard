"""
Unit tests for Phase 4 institutional alpha engine (no network).
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from alpha_engine.alpha_base import AlphaOutput, STATISTICAL_SAFETY
from alpha_engine.alpha_metadata import AlphaMetadata
from alpha_engine.alpha_registry import AlphaRegistry, register_default_alphas
from alpha_engine.cross_sectional.ranking_engine import CrossSectionalRankingEngine
from alpha_engine.momentum.trend_persistence import TrendPersistenceAlpha
from alpha_engine.mean_reversion.zscore_reversion import ZScoreReversionAlpha
from alpha_engine.signal_combination.confidence_aggregation import aggregate_confidence
from alpha_engine.signal_combination.probabilistic_combiner import ProbabilisticCombiner
from pipelines.feature_pipeline import FeaturePipeline


def _features_frame(n: int = 150) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    open_ = close + rng.normal(0, 0.1, n)
    high = np.maximum(open_, close) + rng.uniform(0.05, 0.5, n)
    low = np.minimum(open_, close) - rng.uniform(0.05, 0.5, n)
    ohlcv = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.integers(100, 1000, n).astype(float),
        },
        index=idx,
    )
    return FeaturePipeline().run(ohlcv)


class TestAlphaMetadata(unittest.TestCase):
    def test_metadata_requires_fields(self) -> None:
        meta = AlphaMetadata(
            alpha_name="test_alpha",
            description="Test alpha",
            assumptions=("a1",),
            failure_modes=("f1",),
            regime_dependency=("RANGE",),
            holding_period="short",
            required_features=("close",),
            expected_behavior="Test",
            family="momentum",
        )
        self.assertEqual(meta.alpha_name, "test_alpha")

    def test_empty_name_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AlphaMetadata(
                alpha_name="",
                description="x",
                assumptions=("a",),
                failure_modes=("f",),
                regime_dependency=("R",),
                holding_period="short",
                required_features=("close",),
                expected_behavior="x",
                family="momentum",
            )


class TestAlphaRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = AlphaRegistry()
        self.registry.clear()

    def test_register_defaults(self) -> None:
        register_default_alphas(self.registry)
        names = self.registry.list_names()
        self.assertIn("trend_persistence", names)
        self.assertIn("zscore_reversion", names)
        self.assertGreaterEqual(len(names), 10)

    def test_metadata_integrity(self) -> None:
        register_default_alphas(self.registry)
        for name in self.registry.list_names():
            meta = self.registry.metadata(name)
            self.assertTrue(meta.assumptions)
            self.assertTrue(meta.failure_modes)
            self.assertTrue(meta.required_features)


class TestProbabilisticOutputs(unittest.TestCase):
    def test_output_bounds(self) -> None:
        df = _features_frame(120)
        alpha = TrendPersistenceAlpha()
        out = alpha.compute(df)
        self.assertIsInstance(out, AlphaOutput)
        self.assertGreaterEqual(out.alpha_score, -1.0)
        self.assertLessEqual(out.alpha_score, 1.0)
        self.assertGreaterEqual(out.confidence, 0.0)
        self.assertLessEqual(out.confidence, 1.0)
        self.assertNotIn("BUY", str(out))
        self.assertNotIn("SELL", str(out))

    def test_series_no_lookahead(self) -> None:
        df = _features_frame(100)
        alpha = TrendPersistenceAlpha()
        full = alpha.compute_series(df)
        truncated = alpha.compute_series(df.iloc[:-5])
        common = full.outputs.index.intersection(truncated.outputs.index)
        pd.testing.assert_series_equal(
            full.outputs.loc[common, "alpha_score"],
            truncated.outputs.loc[common, "alpha_score"],
            check_names=False,
        )


class TestRegimeFiltering(unittest.TestCase):
    def test_reversion_penalized_in_trend(self) -> None:
        df = _features_frame(120)
        alpha = ZScoreReversionAlpha()
        series = alpha.compute_series(df)
        self.assertIn("stationarity_gate", [c.replace("feat_", "") for c in series.outputs.columns if "gate" in c])
        self.assertTrue((series.outputs["confidence"] <= 1.0).all())


class TestCrossSectionalRanking(unittest.TestCase):
    def test_ranking_consistency(self) -> None:
        idx = pd.date_range("2023-01-01", periods=80, freq="D", tz="UTC")
        rng = np.random.default_rng(1)
        prices = pd.DataFrame(
            {
                "A": 100 + np.cumsum(rng.normal(0.01, 1, 80)),
                "B": 100 + np.cumsum(rng.normal(0, 1, 80)),
                "C": 100 + np.cumsum(rng.normal(-0.01, 1, 80)),
            },
            index=idx,
        )
        result = CrossSectionalRankingEngine().rank(prices)
        last_ranks = result.ranks.iloc[-1].dropna()
        self.assertEqual(len(last_ranks), 3)
        self.assertAlmostEqual(result.scores.iloc[-1].max(), 1.0, places=1)


class TestVolatilityNormalization(unittest.TestCase):
    def test_vol_adj_momentum_finite(self) -> None:
        from alpha_engine.momentum.volatility_adjusted_momentum import VolatilityAdjustedMomentumAlpha

        df = _features_frame(100)
        out = VolatilityAdjustedMomentumAlpha().compute_series(df)
        scores = out.outputs["alpha_score"].dropna()
        self.assertTrue(np.isfinite(scores).all())


class TestSignalCombination(unittest.TestCase):
    def test_probabilistic_combiner(self) -> None:
        df = _features_frame(100)
        mom = TrendPersistenceAlpha().compute_series(df)
        rev = ZScoreReversionAlpha().compute_series(df)
        combined = ProbabilisticCombiner().combine(
            {"momentum": mom, "reversion": rev},
            vol_series=df["rolling_volatility"],
        )
        self.assertIn("alpha_score", combined.columns)
        self.assertIn("disagreement", combined.columns)
        self.assertTrue((combined["alpha_score"].abs() <= 1.0).all())

    def test_confidence_aggregation(self) -> None:
        agg = aggregate_confidence({"a": 0.8, "b": 0.3, "c": 0.6})
        self.assertLess(agg.min_confidence, agg.mean_confidence)


class TestValidationIntegration(unittest.TestCase):
    def test_validate_hook_runs(self) -> None:
        df = _features_frame(400)
        alpha = TrendPersistenceAlpha()
        series = alpha.compute_series(df)
        signal = series.outputs["alpha_score"].shift(1)
        strat = (signal * df.loc[series.outputs.index, "pct_return"]).dropna()
        report = alpha.validate(strat.iloc[-300:], train_size=126, test_size=42)
        self.assertTrue(len(report.summary) > 0)
        self.assertTrue(len(report.warnings) >= len(STATISTICAL_SAFETY))


if __name__ == "__main__":
    unittest.main()
