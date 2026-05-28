from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd


class MockProvider:
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        period: str | None = None,
    ) -> pd.DataFrame:
        del symbol, timeframe, start, end, period

        n = 512
        ts = pd.date_range(
            end=pd.Timestamp.now(tz="UTC"), periods=n, freq="1h"
        )
        rng = np.random.default_rng(42)
        returns = rng.normal(0, 0.003, size=n)
        close = 100 * np.exp(np.cumsum(returns))
        open_ = np.roll(close, 1)
        open_[0] = close[0]
        high = np.maximum(open_, close) * (1 + rng.uniform(0.0005, 0.004, size=n))
        low = np.minimum(open_, close) * (1 - rng.uniform(0.0005, 0.004, size=n))
        volume = rng.integers(1000, 5000, size=n)

        return pd.DataFrame(
            {
                "timestamp": ts,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            }
        )
