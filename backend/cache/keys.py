"""
Deterministic cache-key construction.

Key format
----------
``{level}:{symbol}:{timeframe}:{range}:{feature_version}``

The ``feature_version`` segment is what makes the cache safe: any change to
feature/regime math bumps ``core.config.FEATURE_VERSION`` and transparently
invalidates every dependent entry without a manual flush. ``level`` (the first
segment) doubles as the metric label and the invalidation prefix.
"""

from __future__ import annotations

from core.config import FEATURE_VERSION

# Canonical cache levels (also used as metric labels and invalidation prefixes).
LEVEL_RAW = "raw"
LEVEL_FEATURE = "feature"
LEVEL_REGIME = "regime"


def make_cache_key(
    *,
    level: str,
    symbol: str,
    timeframe: str,
    data_range: str,
    feature_version: str = FEATURE_VERSION,
) -> str:
    return f"{level}:{symbol}:{timeframe}:{data_range}:{feature_version}"


def level_of(key: str) -> str:
    """Extract the cache level (first segment) from a key."""
    return key.split(":", 1)[0] if ":" in key else key
