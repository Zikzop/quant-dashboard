"""
Data Access Layer (DAL).

The single choke point between "the outside world of vendors" and "our engines".
Responsibilities, in order:

1. Translate a *canonical* request (asset id + canonical timeframe) into
   provider params using the timeframe registry — engines never speak yfinance.
2. Serve cached raw bars when fresh (raw cache level), else fetch.
3. Wrap the provider fetch in reliability (retry -> timeout -> circuit breaker)
   so a flaky or hung feed degrades gracefully instead of cascading.
4. Resample synthetic timeframes (4H from 1h).
5. Validate OHLCV integrity before anything downstream trusts it.
6. Cache the validated, normalized frame.

The DAL is synchronous: FastAPI runs sync routes in a worker thread, and the
heavy engine work downstream is CPU-bound anyway. The async provider coroutine
is driven on a private event loop inside the reliability worker thread, so we
get provider concurrency-readiness without blocking the API event loop.

Output contract (unified schema): a flat DataFrame with columns
``[timestamp, open, high, low, close, volume]``, UTC, sorted, RangeIndex.
No engine imports yfinance — only this module (indirectly via the provider).
"""

from __future__ import annotations

import asyncio
from typing import Callable

import pandas as pd

from assets.registry import AssetDefinition, resolve_symbol
from assets.timeframes import TimeframeSpec, get_timeframe_spec
from cache.keys import LEVEL_RAW, make_cache_key
from cache.store import CacheStore, get_cache_store
from core.config import Settings, get_settings
from core.logging import get_logger
from core.metrics import PROVIDER_ERRORS
from core.reliability import CircuitBreaker, ResilientExecutor, RetryPolicy
from data.providers import get_market_data_provider
from data.providers.utils import REQUIRED_COLUMNS
from validation.ohlcv_validator import OHLCVValidator

logger = get_logger("data.access")


def _run_coro(coro):
    """Drive a coroutine to completion on a fresh loop (worker-thread safe)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MarketDataAccess:
    """Provider-agnostic, cached, validated OHLCV access."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        cache: CacheStore | None = None,
        provider=None,
        validator: OHLCVValidator | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._cache = cache or get_cache_store()
        self._provider = provider or get_market_data_provider()
        self._validator = validator or OHLCVValidator(drop_invalid_rows=True)

        self._executor = ResilientExecutor(
            breaker=CircuitBreaker(
                fail_max=self._settings.provider_breaker_fail_max,
                reset_timeout=self._settings.provider_breaker_reset_seconds,
                name=f"provider:{self._provider_name}",
            ),
            retry=RetryPolicy(max_attempts=self._settings.provider_max_retries),
            timeout=float(self._settings.provider_timeout_seconds),
            label="provider.fetch_ohlcv",
        )

    @property
    def _provider_name(self) -> str:
        return type(self._provider).__name__

    # -- public API ---------------------------------------------------------

    def fetch_ohlcv(
        self,
        symbol_or_id: str | None,
        timeframe: str,
        *,
        use_cache: bool = True,
    ) -> tuple[pd.DataFrame, AssetDefinition, bool]:
        """Return ``(bars, asset, cache_hit)`` for a canonical request."""
        asset = resolve_symbol(symbol_or_id)
        spec = get_timeframe_spec(timeframe)
        key = make_cache_key(
            level=LEVEL_RAW,
            symbol=asset.provider_symbol,
            timeframe=timeframe,
            data_range=spec.yf_period,
        )

        if use_cache:
            cached = self._cache.get_dataframe(key)
            if cached is not None and not cached.empty:
                logger.info(
                    "raw_cache_hit",
                    symbol=asset.provider_symbol,
                    timeframe=timeframe,
                    rows=len(cached),
                )
                return cached, asset, True

        bars = self._fetch_fresh(asset, spec)
        if use_cache and not bars.empty:
            self._cache.set_dataframe(key, bars, ttl=self._settings.ttl_raw_seconds)
        return bars, asset, False

    def fetch_aligned_closes(
        self,
        symbols: dict[str, str],
        *,
        yf_interval: str = "1d",
        yf_period: str = "2y",
    ) -> pd.DataFrame:
        """Fetch and align close prices for an arbitrary symbol universe.

        Used by the cross-asset/intermarket engines. Goes through the provider
        + reliability path (never yfinance directly) so the correlation engine
        is provider-agnostic and works at any timeframe, not just daily.
        """
        key = make_cache_key(
            level=LEVEL_RAW,
            symbol="UNIVERSE-" + "-".join(sorted(symbols.values())),
            timeframe=yf_interval,
            data_range=yf_period,
        )
        cached = self._cache.get_dataframe(key)
        if cached is not None and not cached.empty:
            return cached.set_index("timestamp")

        series: dict[str, pd.Series] = {}
        for label, provider_symbol in symbols.items():
            def fetch(sym: str = provider_symbol) -> pd.DataFrame:
                return _run_coro(
                    self._provider.fetch_ohlcv(
                        symbol=sym, timeframe=yf_interval, period=yf_period
                    )
                )

            try:
                raw = self._executor.run(fetch)
            except Exception as exc:
                PROVIDER_ERRORS.labels(provider=self._provider_name).inc()
                logger.warning(
                    "universe_symbol_fetch_failed",
                    symbol=provider_symbol,
                    error=str(exc),
                )
                continue
            if raw is None or raw.empty:
                continue
            s = raw.set_index("timestamp")["close"]
            s.name = label
            series[label] = s

        if not series:
            raise ValueError("No cross-asset price data returned from provider.")

        prices = pd.DataFrame(series).sort_index().ffill().dropna(how="any")
        if not prices.empty:
            self._cache.set_dataframe(
                key, prices.reset_index(), ttl=self._settings.ttl_raw_seconds
            )
        return prices

    def fetch_close_series(
        self, symbol_or_id: str, timeframe: str
    ) -> pd.Series:
        """Aligned close series (UTC DatetimeIndex) — used by intermarket/correlation."""
        bars, _asset, _hit = self.fetch_ohlcv(symbol_or_id, timeframe)
        if bars.empty:
            return pd.Series(dtype=float)
        s = bars.set_index("timestamp")["close"]
        s.name = symbol_or_id
        return s

    # -- internals ----------------------------------------------------------

    def _fetch_fresh(
        self, asset: AssetDefinition, spec: TimeframeSpec
    ) -> pd.DataFrame:
        def fetch() -> pd.DataFrame:
            return _run_coro(
                self._provider.fetch_ohlcv(
                    symbol=asset.provider_symbol,
                    timeframe=spec.yf_interval,
                    period=spec.yf_period,
                )
            )

        try:
            raw = self._executor.run(fetch)
        except Exception as exc:
            PROVIDER_ERRORS.labels(provider=self._provider_name).inc()
            logger.error(
                "provider_fetch_failed",
                provider=self._provider_name,
                symbol=asset.provider_symbol,
                timeframe=spec.timeframe,
                error=str(exc),
            )
            raise

        if raw is None or raw.empty:
            return pd.DataFrame(columns=REQUIRED_COLUMNS)

        bars = self._maybe_resample(raw, spec)
        bars = self._validate(bars, asset, spec)
        logger.info(
            "raw_fetch_ok",
            provider=self._provider_name,
            symbol=asset.provider_symbol,
            timeframe=spec.timeframe,
            rows=len(bars),
        )
        return bars

    @staticmethod
    def _maybe_resample(bars: pd.DataFrame, spec: TimeframeSpec) -> pd.DataFrame:
        if not spec.resample:
            return bars
        indexed = bars.set_index("timestamp")
        agg = (
            indexed.resample(spec.resample)
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna(subset=["open", "high", "low", "close"])
        )
        return agg.reset_index()

    def _validate(
        self, bars: pd.DataFrame, asset: AssetDefinition, spec: TimeframeSpec
    ) -> pd.DataFrame:
        cleaned, report = self._validator.validate(
            bars, symbol=asset.provider_symbol, interval=spec.yf_interval
        )
        if not report.passed:
            logger.warning(
                "ohlcv_validation_issues",
                symbol=asset.provider_symbol,
                timeframe=spec.timeframe,
                issues=[i.code for i in report.issues],
                input_rows=report.input_rows,
                output_rows=report.output_rows,
            )
        # Return to the unified flat schema (timestamp column, RangeIndex).
        out = cleaned.reset_index()
        if "timestamp" not in out.columns:
            idx_name = cleaned.index.name or "index"
            if idx_name in out.columns:
                out = out.rename(columns={idx_name: "timestamp"})
        if "timestamp" not in out.columns and "Datetime" in out.columns:
            out = out.rename(columns={"Datetime": "timestamp"})
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
        out = out.dropna(subset=["timestamp"])
        return out[REQUIRED_COLUMNS].sort_values("timestamp").reset_index(drop=True)


_DAL: MarketDataAccess | None = None


def get_market_data_access() -> MarketDataAccess:
    global _DAL
    if _DAL is None:
        _DAL = MarketDataAccess()
    return _DAL


def reset_market_data_access() -> None:
    """Test hook: drop the singleton so a new provider/cache can be injected."""
    global _DAL
    _DAL = None
