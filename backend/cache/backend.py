"""
Low-level cache backends operating on raw bytes.

Three implementations, selected automatically:
* ``RedisBackend`` — when ``REDIS_URL`` is set and ``redis`` importable. Shared,
  network-addressable, native TTL — the production choice for multi-worker /
  multi-host deployments.
* ``DiskBackend``  — filesystem fallback with embedded expiry. Survives process
  restarts, requires no external service. Default for single-node / dev.
* ``NullBackend``  — disables caching entirely (cache_enabled=False or as a
  last-resort fallback) without changing call sites.

Backends speak bytes only; (de)serialization (parquet/JSON) lives in
``cache.store``. This separation keeps the storage layer dumb and swappable.
"""

from __future__ import annotations

import hashlib
import os
import struct
import time
from pathlib import Path
from typing import Iterator, Protocol

from core.logging import get_logger

logger = get_logger("cache.backend")


class CacheBackend(Protocol):
    def get(self, key: str) -> bytes | None: ...
    def set(self, key: str, value: bytes, ttl: int | None = None) -> None: ...
    def delete(self, key: str) -> None: ...
    def delete_prefix(self, prefix: str) -> int: ...
    @property
    def name(self) -> str: ...


class NullBackend:
    @property
    def name(self) -> str:
        return "null"

    def get(self, key: str) -> bytes | None:
        return None

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        return None

    def delete(self, key: str) -> None:
        return None

    def delete_prefix(self, prefix: str) -> int:
        return 0


class DiskBackend:
    """Filesystem cache with embedded expiry and prefix invalidation.

    Envelope layout per entry file:
        [8 bytes: expiry epoch (0 = never)][4 bytes: key length][key][payload]
    The original key is embedded so prefix invalidation can match without an
    external index. Filenames are sha1 hashes to stay filesystem-safe.
    """

    _MAGIC = b"QCV1"

    def __init__(self, cache_dir: str) -> None:
        self._dir = Path(cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    @property
    def name(self) -> str:
        return "disk"

    def _path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
        return self._dir / f"{digest}.qc"

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            raw = path.read_bytes()
            magic, expiry, key_len = (
                raw[:4],
                struct.unpack(">q", raw[4:12])[0],
                struct.unpack(">I", raw[12:16])[0],
            )
            if magic != self._MAGIC:
                return None
            if expiry != 0 and time.time() > expiry:
                path.unlink(missing_ok=True)
                return None
            payload_start = 16 + key_len
            return raw[payload_start:]
        except Exception:
            logger.warning("disk_cache_read_failed", key=key)
            return None

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        expiry = int(time.time() + ttl) if ttl else 0
        key_bytes = key.encode("utf-8")
        envelope = (
            self._MAGIC
            + struct.pack(">q", expiry)
            + struct.pack(">I", len(key_bytes))
            + key_bytes
            + value
        )
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(envelope)
        os.replace(tmp, path)  # atomic publish

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def _iter_entries(self) -> Iterator[tuple[Path, str]]:
        for path in self._dir.glob("*.qc"):
            try:
                with path.open("rb") as fh:
                    header = fh.read(16)
                    if len(header) < 16 or header[:4] != self._MAGIC:
                        continue
                    key_len = struct.unpack(">I", header[12:16])[0]
                    key = fh.read(key_len).decode("utf-8", errors="ignore")
                yield path, key
            except Exception:
                continue

    def delete_prefix(self, prefix: str) -> int:
        removed = 0
        for path, key in self._iter_entries():
            if key.startswith(prefix):
                path.unlink(missing_ok=True)
                removed += 1
        return removed


class RedisBackend:
    def __init__(self, url: str) -> None:
        import redis  # imported lazily; only when selected

        self._client = redis.Redis.from_url(url)
        self._client.ping()

    @property
    def name(self) -> str:
        return "redis"

    def get(self, key: str) -> bytes | None:
        return self._client.get(key)

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        if ttl:
            self._client.set(key, value, ex=ttl)
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def delete_prefix(self, prefix: str) -> int:
        removed = 0
        for k in self._client.scan_iter(match=f"{prefix}*"):
            self._client.delete(k)
            removed += 1
        return removed


def build_backend(
    *,
    redis_url: str | None,
    cache_dir: str,
    enabled: bool = True,
) -> CacheBackend:
    """Select a backend with graceful degradation Redis -> Disk -> Null."""
    if not enabled:
        logger.info("cache_disabled")
        return NullBackend()
    if redis_url:
        try:
            backend = RedisBackend(redis_url)
            logger.info("cache_backend_selected", backend="redis")
            return backend
        except Exception as exc:
            logger.warning("redis_unavailable_fallback_disk", error=str(exc))
    try:
        backend = DiskBackend(cache_dir)
        logger.info("cache_backend_selected", backend="disk", cache_dir=cache_dir)
        return backend
    except Exception as exc:  # pragma: no cover
        logger.error("disk_cache_unavailable_fallback_null", error=str(exc))
        return NullBackend()
