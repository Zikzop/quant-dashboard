"""
High-level typed cache.

Serializes the two payload shapes the platform caches:
* DataFrames (raw bars, feature frames) -> Parquet bytes (columnar, typed,
  preserves dtypes and the index).
* JSON-able dicts (regime/pipeline outputs) -> UTF-8 JSON bytes.

Every access emits a hit/miss metric and a structured log line keyed by cache
level, satisfying the "cache hit/miss logging exists" acceptance criterion.
TTL and prefix-based invalidation are delegated to the backend.
"""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd

from cache.backend import CacheBackend, build_backend
from cache.keys import level_of
from core.config import Settings, get_settings
from core.logging import get_logger
from core.metrics import record_cache

logger = get_logger("cache.store")


class CacheStore:
    def __init__(self, backend: CacheBackend, settings: Settings | None = None) -> None:
        self._backend = backend
        self._settings = settings or get_settings()

    @property
    def backend_name(self) -> str:
        return self._backend.name

    # -- DataFrame (parquet) ------------------------------------------------

    def get_dataframe(self, key: str) -> pd.DataFrame | None:
        raw = self._backend.get(key)
        hit = raw is not None
        self._observe(key, hit)
        if not hit:
            return None
        try:
            return pd.read_parquet(io.BytesIO(raw))
        except Exception:
            logger.warning("cache_parquet_decode_failed", key=key)
            self._backend.delete(key)
            return None

    def set_dataframe(self, key: str, df: pd.DataFrame, ttl: int | None = None) -> None:
        try:
            buf = io.BytesIO()
            df.to_parquet(buf, engine="pyarrow")
            self._backend.set(key, buf.getvalue(), ttl=ttl)
        except Exception as exc:
            logger.warning("cache_parquet_encode_failed", key=key, error=str(exc))

    # -- JSON ---------------------------------------------------------------

    def get_json(self, key: str) -> Any | None:
        raw = self._backend.get(key)
        hit = raw is not None
        self._observe(key, hit)
        if not hit:
            return None
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            logger.warning("cache_json_decode_failed", key=key)
            self._backend.delete(key)
            return None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        try:
            payload = json.dumps(value, default=str, separators=(",", ":")).encode("utf-8")
            self._backend.set(key, payload, ttl=ttl)
        except Exception as exc:
            logger.warning("cache_json_encode_failed", key=key, error=str(exc))

    # -- Invalidation -------------------------------------------------------

    def invalidate(self, key: str) -> None:
        self._backend.delete(key)
        logger.info("cache_invalidate", key=key)

    def invalidate_prefix(self, prefix: str) -> int:
        n = self._backend.delete_prefix(prefix)
        logger.info("cache_invalidate_prefix", prefix=prefix, removed=n)
        return n

    # -- internals ----------------------------------------------------------

    def _observe(self, key: str, hit: bool) -> None:
        level = level_of(key)
        record_cache(level, hit)
        logger.debug("cache_lookup", key=key, level=level, result="hit" if hit else "miss")


_STORE: CacheStore | None = None


def get_cache_store() -> CacheStore:
    """Process-wide cache store singleton built from current settings."""
    global _STORE
    if _STORE is None:
        settings = get_settings()
        backend = build_backend(
            redis_url=settings.redis_url,
            cache_dir=settings.cache_dir,
            enabled=settings.cache_enabled,
        )
        _STORE = CacheStore(backend, settings)
    return _STORE
