"""
Parquet persistence for tiered market data.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional, Union

import pandas as pd

from config.data_paths import DataPaths, get_data_paths

logger = logging.getLogger(__name__)


def _sanitize_symbol(symbol: str) -> str:
    """Filesystem-safe symbol token for parquet filenames."""
    return re.sub(r"[^\w\-.]+", "_", symbol.strip())


class ParquetHandler:
    """
    Save and load OHLCV / feature DataFrames as parquet.

    File naming: {SYMBOL}_{INTERVAL}.parquet
    """

    def __init__(self, base_dir: Union[Path, str], paths: Optional[DataPaths] = None):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._paths = paths or get_data_paths()

    @classmethod
    def for_tier(cls, tier: str, paths: Optional[DataPaths] = None) -> "ParquetHandler":
        paths = paths or get_data_paths()
        tier_map = {
            "raw": paths.raw,
            "clean": paths.clean,
            "normalized": paths.normalized,
            "features": paths.features,
        }
        if tier not in tier_map:
            raise ValueError(f"Unknown tier: {tier}. Expected one of {list(tier_map)}")
        return cls(tier_map[tier], paths=paths)

    def build_filename(self, symbol: str, interval: str) -> str:
        safe_symbol = _sanitize_symbol(symbol)
        safe_interval = interval.replace("/", "_")
        return f"{safe_symbol}_{safe_interval}.parquet"

    def resolve_path(self, symbol: str, interval: str) -> Path:
        return self.base_dir / self.build_filename(symbol, interval)

    def save(
        self,
        df: pd.DataFrame,
        symbol: str,
        interval: str,
        *,
        index: bool = True,
    ) -> Path:
        path = self.resolve_path(symbol, interval)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, engine="pyarrow", index=index)
        logger.info("Saved parquet %s rows=%d", path, len(df))
        return path

    def load(
        self,
        symbol: str,
        interval: str,
    ) -> pd.DataFrame:
        path = self.resolve_path(symbol, interval)
        if not path.exists():
            raise FileNotFoundError(f"Parquet not found: {path}")
        df = pd.read_parquet(path, engine="pyarrow")
        logger.info("Loaded parquet %s rows=%d", path, len(df))
        return df

    def exists(self, symbol: str, interval: str) -> bool:
        return self.resolve_path(symbol, interval).exists()
