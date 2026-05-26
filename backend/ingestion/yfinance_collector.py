"""
Yahoo Finance OHLCV ingestion adapter.

Designed as a pluggable source for the data pipeline; future sources
(Databento, Rithmic, websockets) should implement the same return contract.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_SYMBOL = "GC=F"


@dataclass(frozen=True)
class YFinanceCollectorConfig:
    symbol: str = DEFAULT_SYMBOL
    interval: str = "1d"
    period: str = "2y"
    auto_adjust: bool = True


class YFinanceCollector:
    """Fetch OHLCV history from yfinance."""

    def __init__(self, config: Optional[YFinanceCollectorConfig] = None) -> None:
        self.config = config or YFinanceCollectorConfig()

    def collect(self) -> pd.DataFrame:
        """
        Download OHLCV for configured symbol.

        Returns
        -------
        pd.DataFrame
            Index: DatetimeIndex (vendor timezone).
            Columns: Open, High, Low, Close, Volume (Title Case).

        Raises
        ------
        ValueError
            Empty or malformed vendor response.
        RuntimeError
            Network or vendor failure.
        """
        symbol = self.config.symbol
        logger.info(
            "Collecting yfinance data symbol=%s interval=%s period=%s",
            symbol,
            self.config.interval,
            self.config.period,
        )

        try:
            raw = yf.download(
                symbol,
                period=self.config.period,
                interval=self.config.interval,
                progress=False,
                auto_adjust=self.config.auto_adjust,
            )
        except Exception as exc:
            logger.exception("yfinance download failed for %s", symbol)
            raise RuntimeError(
                f"yfinance download failed for {symbol}"
            ) from exc

        if raw is None or raw.empty:
            raise ValueError(f"No data returned for symbol={symbol}")

        df = self._flatten_columns(raw)
        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"Missing OHLCV columns for {symbol}: {sorted(missing)}"
            )

        df = df[list(required)].copy()
        df.index.name = "timestamp"
        logger.info("Collected %d bars for %s", len(df), symbol)
        return df

    @staticmethod
    def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
        if isinstance(df.columns, pd.MultiIndex):
            df = df.copy()
            df.columns = df.columns.get_level_values(0)
        return df
