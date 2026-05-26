"""
Unified parquet dataset loader for institutional research workflows.

All research modules must load data through this interface to avoid
duplicated I/O logic and schema drift across tiers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Sequence

import pandas as pd

from config.data_paths import DataPaths, get_data_paths
from storage.parquet_handler import ParquetHandler

logger = logging.getLogger(__name__)

OHLCV_COLUMNS = frozenset({"open", "high", "low", "close", "volume"})
FEATURE_COLUMNS = frozenset(
    {
        "log_return",
        "pct_return",
        "rolling_mean",
        "z_score",
        "rolling_volatility",
        "realized_volatility",
        "atr",
    }
)


class DatasetTier(str, Enum):
    CLEAN = "clean"
    NORMALIZED = "normalized"
    FEATURES = "features"


@dataclass(frozen=True)
class DatasetLoaderConfig:
    """Configuration for dataset loading and validation."""

    tier: DatasetTier = DatasetTier.FEATURES
    enforce_utc: bool = True
    require_monotonic: bool = True
    drop_duplicate_timestamps: bool = True


class DatasetLoader:
    """
    Load symbol/interval parquet datasets from clean, normalized, or features tiers.

    Returns a canonical DataFrame with UTC DatetimeIndex named ``timestamp``.
    """

    TIER_SCHEMA: dict[DatasetTier, frozenset[str]] = {
        DatasetTier.CLEAN: OHLCV_COLUMNS,
        DatasetTier.NORMALIZED: OHLCV_COLUMNS,
        DatasetTier.FEATURES: OHLCV_COLUMNS | FEATURE_COLUMNS,
    }

    def __init__(
        self,
        config: DatasetLoaderConfig | None = None,
        paths: DataPaths | None = None,
    ) -> None:
        self.config = config or DatasetLoaderConfig()
        self._paths = paths or get_data_paths()
        self._handler = ParquetHandler.for_tier(self.config.tier.value, paths=self._paths)

    def load(
        self,
        symbol: str,
        interval: str,
        *,
        start: datetime | pd.Timestamp | None = None,
        end: datetime | pd.Timestamp | None = None,
        columns: Sequence[str] | None = None,
    ) -> pd.DataFrame:
        """
        Load a dataset and return a validated canonical frame.

        Parameters
        ----------
        symbol : str
            Instrument symbol (e.g. ``GC=F``).
        interval : str
            Bar interval (e.g. ``1d``).
        start, end : optional
            Inclusive UTC date bounds applied after load.
        columns : optional
            Subset of columns to retain (must exist in tier schema).

        Returns
        -------
        pd.DataFrame
            UTC-indexed frame sorted ascending by timestamp.
        """
        raw = self._handler.load(symbol, interval)
        df = self._to_canonical_index(raw)
        self._validate_schema(df, self.config.tier)

        if self.config.drop_duplicate_timestamps and df.index.has_duplicates:
            before = len(df)
            df = df[~df.index.duplicated(keep="last")]
            logger.warning(
                "Dropped %d duplicate timestamps for %s/%s",
                before - len(df),
                symbol,
                interval,
            )

        if self.config.require_monotonic and not df.index.is_monotonic_increasing:
            df = df.sort_index()
            logger.warning("Sorted non-monotonic timestamps for %s/%s", symbol, interval)

        if start is not None or end is not None:
            df = self._apply_date_filter(df, start, end)

        if columns is not None:
            missing = set(columns) - set(df.columns)
            if missing:
                raise ValueError(f"Requested columns not in dataset: {sorted(missing)}")
            df = df.loc[:, list(columns)]

        logger.info(
            "Loaded %s/%s tier=%s rows=%d cols=%d",
            symbol,
            interval,
            self.config.tier.value,
            len(df),
            len(df.columns),
        )
        return df

    def exists(self, symbol: str, interval: str) -> bool:
        """Return True if parquet exists for symbol/interval."""
        return self._handler.exists(symbol, interval)

    def resolve_path(self, symbol: str, interval: str):
        """Return on-disk parquet path."""
        return self._handler.resolve_path(symbol, interval)

    @staticmethod
    def _to_canonical_index(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if "timestamp" in out.columns:
            ts = pd.to_datetime(out["timestamp"], utc=True)
            out = out.drop(columns=["timestamp"])
            out.index = pd.DatetimeIndex(ts, name="timestamp")
        elif isinstance(out.index, pd.DatetimeIndex):
            if out.index.tz is None:
                out.index = out.index.tz_localize("UTC")
            else:
                out.index = out.index.tz_convert("UTC")
            out.index.name = "timestamp"
        else:
            raise ValueError("Dataset must have DatetimeIndex or timestamp column")

        out.columns = [str(c).lower() for c in out.columns]
        return out.sort_index()

    def _validate_schema(self, df: pd.DataFrame, tier: DatasetTier) -> None:
        required = self.TIER_SCHEMA[tier]
        cols = set(df.columns)
        missing = required - cols
        if missing:
            raise ValueError(
                f"Tier '{tier.value}' missing required columns: {sorted(missing)}"
            )
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Canonical frame requires DatetimeIndex")
        if self.config.enforce_utc and str(df.index.tz) != "UTC":
            raise ValueError("Index must be UTC")

    @staticmethod
    def _apply_date_filter(
        df: pd.DataFrame,
        start: datetime | pd.Timestamp | None,
        end: datetime | pd.Timestamp | None,
    ) -> pd.DataFrame:
        out = df
        if start is not None:
            start_ts = pd.Timestamp(start).tz_convert("UTC") if pd.Timestamp(start).tzinfo else pd.Timestamp(start, tz="UTC")
            out = out.loc[out.index >= start_ts]
        if end is not None:
            end_ts = pd.Timestamp(end).tz_convert("UTC") if pd.Timestamp(end).tzinfo else pd.Timestamp(end, tz="UTC")
            out = out.loc[out.index <= end_ts]
        if out.empty:
            raise ValueError("Date filter returned empty dataset")
        return out
