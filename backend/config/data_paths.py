"""
Central path resolution for on-disk market data tiers.

Layout (under backend/data/):
    raw/         — optional raw vendor dumps
    clean/       — validated + normalized OHLCV parquet
    normalized/  — alias tier for normalized snapshots (pipeline may mirror clean)
    features/    — research feature parquet
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class DataPaths:
    root: Path
    raw: Path
    clean: Path
    normalized: Path
    features: Path

    def ensure_all(self) -> None:
        for path in (self.raw, self.clean, self.normalized, self.features):
            path.mkdir(parents=True, exist_ok=True)


def get_data_paths() -> DataPaths:
    root = _backend_root() / "data"
    return DataPaths(
        root=root,
        raw=root / "raw",
        clean=root / "clean",
        normalized=root / "normalized",
        features=root / "features",
    )
