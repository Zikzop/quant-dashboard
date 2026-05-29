"""
OHLCV normalization: UTC timestamps, canonical schema, chronological order.
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

CANONICAL_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


class NormalizationPipeline:
    """Transform vendor OHLCV into institutional canonical schema."""

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize vendor frame to UTC-indexed lowercase OHLCV.

        Parameters
        ----------
        df : pd.DataFrame
            Vendor format (DatetimeIndex + Title Case columns).

        Returns
        -------
        pd.DataFrame
            Columns: open, high, low, close, volume
            Index: UTC DatetimeIndex (name=timestamp)
        """
        if df.empty:
            raise ValueError("Cannot normalize empty dataframe")

        working = df.copy()
        working = self._flatten_vendor_columns(working)
        working = self._to_utc_index(working)
        working = self._rename_columns(working)
        working = self._sort_and_dedupe(working)
        working = self._cast_dtypes(working)

        logger.info("Normalized %d OHLCV bars", len(working))
        return working

    @staticmethod
    def _flatten_vendor_columns(df: pd.DataFrame) -> pd.DataFrame:
        if isinstance(df.columns, pd.MultiIndex):
            df = df.copy()
            df.columns = df.columns.get_level_values(0)
        return df

    @staticmethod
    def _to_utc_index(df: pd.DataFrame) -> pd.DataFrame:
        if "timestamp" in df.columns:
            idx = pd.to_datetime(df["timestamp"], utc=True)
            out = df.drop(columns=["timestamp"])
            out.index = idx
        else:
            out = df.copy()
            out.index = pd.to_datetime(out.index, utc=True)

        if out.index.tz is None:
            out.index = out.index.tz_localize("UTC")
        else:
            out.index = out.index.tz_convert("UTC")

        out.index.name = "timestamp"
        return out

    @staticmethod
    def _rename_columns(df: pd.DataFrame) -> pd.DataFrame:
        mapping = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
        renamed = df.rename(columns={k: v for k, v in mapping.items() if k in df.columns})
        lower = {c: c.lower() for c in renamed.columns}
        renamed = renamed.rename(columns=lower)

        missing = set(CANONICAL_COLUMNS[1:]) - set(renamed.columns)
        if missing:
            raise ValueError(f"Missing OHLCV columns after rename: {sorted(missing)}")

        return renamed[list(CANONICAL_COLUMNS[1:])].copy()

    @staticmethod
    def _sort_and_dedupe(df: pd.DataFrame) -> pd.DataFrame:
        sorted_df = df.sort_index()
        dup_count = int(sorted_df.index.duplicated().sum())
        if dup_count:
            logger.warning("Removing %d duplicate timestamps (keep last)", dup_count)
            sorted_df = sorted_df[~sorted_df.index.duplicated(keep="last")]
        return sorted_df

    @staticmethod
    def _cast_dtypes(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for col in ("open", "high", "low", "close", "volume"):
            out[col] = pd.to_numeric(out[col], errors="raise").astype("float64")
        return out

    def to_timestamp_column(self, df: pd.DataFrame) -> pd.DataFrame:
        """Export frame with explicit timestamp column for parquet / pydantic."""
        out = df.reset_index()
        if out.columns[0] != "timestamp":
            out = out.rename(columns={out.columns[0]: "timestamp"})
        other_cols = [c for c in out.columns if c != "timestamp"]
        return out[["timestamp", *other_cols]]
