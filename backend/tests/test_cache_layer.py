"""Cache layer tests: disk backend, TTL, prefix invalidation, typed store."""

from __future__ import annotations

import time

import pandas as pd

from cache.backend import DiskBackend, NullBackend, build_backend
from cache.keys import LEVEL_RAW, LEVEL_REGIME, level_of, make_cache_key
from cache.store import CacheStore


def test_cache_key_format_and_level():
    key = make_cache_key(level=LEVEL_RAW, symbol="BTC-USD", timeframe="1H", data_range="7d")
    assert key.startswith("raw:BTC-USD:1H:7d:")
    assert level_of(key) == "raw"


def test_disk_backend_roundtrip_and_ttl(tmp_path):
    be = DiskBackend(str(tmp_path))
    be.set("k", b"value", ttl=10)
    assert be.get("k") == b"value"

    be.set("expiring", b"x", ttl=1)
    time.sleep(1.1)
    assert be.get("expiring") is None


def test_disk_backend_prefix_invalidation(tmp_path):
    be = DiskBackend(str(tmp_path))
    be.set("regime:BTC:1D:2y:v1", b"a")
    be.set("regime:BTC:1H:7d:v1", b"b")
    be.set("raw:BTC:1D:2y:v1", b"c")
    removed = be.delete_prefix("regime:BTC")
    assert removed == 2
    assert be.get("raw:BTC:1D:2y:v1") == b"c"


def test_store_dataframe_roundtrip(tmp_path):
    store = CacheStore(DiskBackend(str(tmp_path)))
    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=4, freq="h", tz="UTC"),
            "open": [1.0, 2.0, 3.0, 4.0],
            "close": [1.1, 2.1, 3.1, 4.1],
        }
    )
    key = make_cache_key(level=LEVEL_RAW, symbol="BTC", timeframe="1H", data_range="7d")
    assert store.get_dataframe(key) is None  # miss
    store.set_dataframe(key, df, ttl=30)
    out = store.get_dataframe(key)
    assert out is not None and out.equals(df)


def test_store_json_roundtrip_and_invalidate(tmp_path):
    store = CacheStore(DiskBackend(str(tmp_path)))
    key = make_cache_key(level=LEVEL_REGIME, symbol="BTC", timeframe="1D", data_range="2y")
    store.set_json(key, {"regime": "TRENDING", "p": 0.7}, ttl=30)
    assert store.get_json(key) == {"regime": "TRENDING", "p": 0.7}
    store.invalidate(key)
    assert store.get_json(key) is None


def test_null_backend_disables_cache():
    store = CacheStore(NullBackend())
    key = make_cache_key(level=LEVEL_RAW, symbol="BTC", timeframe="1H", data_range="7d")
    store.set_json(key, {"x": 1})
    assert store.get_json(key) is None


def test_build_backend_falls_back_to_disk(tmp_path):
    # No redis_url -> disk backend chosen.
    be = build_backend(redis_url=None, cache_dir=str(tmp_path), enabled=True)
    assert be.name == "disk"
    # Disabled -> null backend.
    assert build_backend(redis_url=None, cache_dir=str(tmp_path), enabled=False).name == "null"
