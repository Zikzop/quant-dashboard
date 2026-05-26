"""
Unit tests for market data infrastructure (no network).
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config.data_paths import DataPaths
from pipelines.feature_pipeline import FeaturePipeline, FeaturePipelineConfig
from pipelines.normalization_pipeline import NormalizationPipeline
from storage.parquet_handler import ParquetHandler
from validation.ohlcv_validator import OHLCVValidator


def _vendor_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=5, freq="D", tz="America/New_York")
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0, 104.0],
            "High": [101.0, 102.0, 103.0, 104.0, 105.0],
            "Low": [99.0, 100.0, 101.0, 102.0, 103.0],
            "Close": [100.5, 101.5, 102.5, 103.5, 104.5],
            "Volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=idx,
    )


def _normalized_frame() -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=30, freq="D", tz="UTC")
    rng = np.random.default_rng(42)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=len(idx)))
    open_ = close + rng.normal(0, 0.2, len(idx))
    high = np.maximum(open_, close) + rng.uniform(0.1, 1.0, len(idx))
    low = np.minimum(open_, close) - rng.uniform(0.1, 1.0, len(idx))
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.integers(100, 1000, len(idx)).astype(float),
        },
        index=idx,
    )


class TestNormalizationPipeline(unittest.TestCase):
    def test_utc_and_column_names(self) -> None:
        normalizer = NormalizationPipeline()
        out = normalizer.run(_vendor_frame())

        self.assertListEqual(
            list(out.columns),
            ["open", "high", "low", "close", "volume"],
        )
        self.assertEqual(str(out.index.tz), "UTC")
        self.assertTrue(out.index.is_monotonic_increasing)

    def test_duplicate_removal(self) -> None:
        df = _vendor_frame()
        dup = pd.concat([df, df.iloc[[-1]]])
        out = NormalizationPipeline().run(dup)
        self.assertEqual(len(out), len(df))


class TestOHLCVValidator(unittest.TestCase):
    def test_detects_invalid_high_low(self) -> None:
        df = _normalized_frame()
        df.iloc[5, df.columns.get_loc("high")] = df.iloc[5]["low"] - 1.0

        clean, report = OHLCVValidator().validate(df, symbol="TEST", interval="1d")
        self.assertFalse(report.passed)
        self.assertTrue(any(i.code == "HIGH_BELOW_LOW" for i in report.issues))
        self.assertNotIn(df.index[5], clean.index)

    def test_monotonic_after_validation(self) -> None:
        clean, report = OHLCVValidator().validate(
            _normalized_frame(), symbol="TEST", interval="1d"
        )
        self.assertTrue(report.passed)
        self.assertTrue(clean.index.is_monotonic_increasing)


class TestParquetHandler(unittest.TestCase):
    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            handler = ParquetHandler(Path(tmp) / "clean")
            df = NormalizationPipeline().to_timestamp_column(_normalized_frame())
            handler.save(df, "GC=F", "1d", index=False)
            loaded = handler.load("GC=F", "1d")
            self.assertEqual(len(loaded), len(df))
            self.assertIn("close", loaded.columns)


class TestFeaturePipeline(unittest.TestCase):
    def test_features_no_lookahead(self) -> None:
        df = _normalized_frame()
        features = FeaturePipeline().run(df)

        self.assertIn("log_return", features.columns)
        self.assertIn("atr", features.columns)
        self.assertTrue(np.isnan(features["log_return"].iloc[0]))
        self.assertFalse(np.isnan(features["log_return"].iloc[-1]))

    def test_rolling_uses_past_only(self) -> None:
        df = _normalized_frame()
        out = FeaturePipeline(
            FeaturePipelineConfig(
                vol_window=5,
                mean_window=5,
                zscore_window=5,
                atr_window=5,
            )
        ).run(df)
        self.assertTrue(np.isnan(out["rolling_mean"].iloc[3]))
        self.assertFalse(np.isnan(out["rolling_mean"].iloc[4]))


class TestTimestampUTC(unittest.TestCase):
    def test_export_timestamp_column(self) -> None:
        normalizer = NormalizationPipeline()
        norm = normalizer.run(_vendor_frame())
        exported = normalizer.to_timestamp_column(norm)
        ts = exported["timestamp"].iloc[0]
        self.assertEqual(ts.tzinfo, timezone.utc)


if __name__ == "__main__":
    unittest.main()
