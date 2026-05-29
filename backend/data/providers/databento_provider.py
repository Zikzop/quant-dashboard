from __future__ import annotations

from datetime import datetime

import pandas as pd


class DatabentoProvider:
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        period: str | None = None,
    ) -> pd.DataFrame:
        del symbol, timeframe, start, end, period
        raise NotImplementedError(
            "DatabentoProvider is a placeholder for future institutional feed integration."
        )
