from __future__ import annotations

from datetime import datetime
from typing import Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        period: str | None = None,
    ) -> pd.DataFrame:
        """
        Return normalized OHLCV with required columns:
        timestamp, open, high, low, close, volume
        """
