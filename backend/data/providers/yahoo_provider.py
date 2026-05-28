from __future__ import annotations

import asyncio
from datetime import datetime

import pandas as pd
import yfinance as yf

from data.providers.utils import normalize_ohlcv_frame


class YahooProvider:
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start: datetime | None = None,
        end: datetime | None = None,
        period: str | None = None,
    ) -> pd.DataFrame:
        kwargs: dict[str, object] = {
            "interval": timeframe,
            "progress": False,
            "auto_adjust": False,
        }
        if period is not None:
            kwargs["period"] = period
        if start is not None:
            kwargs["start"] = start
        if end is not None:
            kwargs["end"] = end

        raw = await asyncio.to_thread(yf.download, symbol, **kwargs)
        return normalize_ohlcv_frame(raw)
