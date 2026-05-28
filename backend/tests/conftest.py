"""
Shared pytest configuration for the institutional-platform test suite.

Forces deterministic, offline conditions: the MockProvider (no network), a
per-session temp cache dir, single-threaded BLAS/loky (so HMM/GARCH fits are
reproducible and warning-free). Env is set *before* any backend import so the
cached ``Settings`` singleton picks it up.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault("MARKET_DATA_PROVIDER", "mock")
os.environ.setdefault("CACHE_DIR", tempfile.mkdtemp(prefix="qc-test-cache-"))
os.environ.setdefault("LOG_LEVEL", "ERROR")
os.environ.setdefault("LOG_JSON", "true")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
os.environ.setdefault("ARROW_DISABLE_CPU_INFO", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(scope="session")
def synthetic_ohlcv() -> pd.DataFrame:
    """Deterministic title-case engine OHLCV frame (UTC DatetimeIndex)."""
    rng = np.random.default_rng(42)
    n = 400
    idx = pd.date_range("2023-01-01", periods=n, freq="h", tz="UTC")
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = np.maximum(open_, close) * (1 + rng.uniform(0.0005, 0.003, n))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.0005, 0.003, n))
    volume = rng.integers(1000, 5000, n).astype(float)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


@pytest.fixture(scope="session")
def synthetic_bars(synthetic_ohlcv: pd.DataFrame) -> pd.DataFrame:
    """The same data in the unified flat provider schema."""
    df = synthetic_ohlcv.reset_index().rename(columns={"index": "timestamp"})
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    return df[["timestamp", "open", "high", "low", "close", "volume"]]
