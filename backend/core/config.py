"""
Centralized, environment-driven configuration.

Design notes
------------
* A single immutable ``Settings`` object is the source of truth for every
  tunable knob (provider, cache, TTLs, feature version, log level). Engines and
  pipelines never read ``os.environ`` directly — they receive ``Settings`` or
  the value they need. This makes behaviour reproducible and test-overridable.
* ``FEATURE_VERSION`` lives here because it participates in cache keys: bumping
  it transparently invalidates every cached feature/regime output without
  manual cache flushes. Any change to feature math MUST bump this.
* No dependency on pydantic-settings (not guaranteed installed); a frozen
  dataclass with an ``from_env`` constructor is sufficient and dependency-free.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

# Bump whenever feature/regime computation changes in a way that should
# invalidate cached outputs. Participates in every cache key.
FEATURE_VERSION = "v1"


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration resolved once at process start."""

    # Data provider selection (yahoo | mock | databento)
    market_data_provider: str = "yahoo"

    # Cache backend
    redis_url: str | None = None
    cache_dir: str = ".cache"
    cache_enabled: bool = True

    # TTLs (seconds) per cache level. Raw bars are refreshed often; regime
    # outputs are expensive and tolerate slightly staler reads.
    ttl_raw_seconds: int = 300
    ttl_feature_seconds: int = 600
    ttl_regime_seconds: int = 900

    # Reliability — provider fetch
    provider_timeout_seconds: int = 20
    provider_max_retries: int = 3
    provider_breaker_fail_max: int = 5
    provider_breaker_reset_seconds: int = 30

    # Observability
    log_level: str = "INFO"
    log_json: bool = True
    feature_version: str = FEATURE_VERSION

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            market_data_provider=os.getenv("MARKET_DATA_PROVIDER", "yahoo").strip().lower(),
            redis_url=(os.getenv("REDIS_URL") or None),
            cache_dir=os.getenv("CACHE_DIR", ".cache"),
            cache_enabled=_env_bool("CACHE_ENABLED", True),
            ttl_raw_seconds=_env_int("CACHE_TTL_RAW", 300),
            ttl_feature_seconds=_env_int("CACHE_TTL_FEATURE", 600),
            ttl_regime_seconds=_env_int("CACHE_TTL_REGIME", 900),
            provider_timeout_seconds=_env_int("PROVIDER_TIMEOUT", 20),
            provider_max_retries=_env_int("PROVIDER_MAX_RETRIES", 3),
            provider_breaker_fail_max=_env_int("PROVIDER_BREAKER_FAIL_MAX", 5),
            provider_breaker_reset_seconds=_env_int("PROVIDER_BREAKER_RESET", 30),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
            log_json=_env_bool("LOG_JSON", True),
            feature_version=os.getenv("FEATURE_VERSION", FEATURE_VERSION),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process-wide singleton. Cached so every layer sees identical config."""
    return Settings.from_env()
