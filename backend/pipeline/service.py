"""
Market-intelligence service: the orchestration seam the API depends on.

Composes the data-access layer, the deterministic pipeline, the regime-level
cache, and the cross-asset correlation overlay into a single call. This is the
only object ``main.py`` needs to know about, which keeps the HTTP layer thin.

Caching strategy
----------------
* Raw bars      -> cached by the DAL (raw level).
* Regime output -> the *entire* computed payload (features + regimes +
  transition matrix + correlation) is cached as one JSON blob (regime level).

Caching the whole computed payload as one entry is a deliberate choice: it
guarantees a response's indicators, regimes, and transition matrix all come
from the same feature generation (no Frankenstein mix of cache generations),
which matters for research reproducibility. ``FEATURE_VERSION`` in the key makes
this safe to evolve.
"""

from __future__ import annotations

from assets.registry import resolve_symbol
from assets.timeframes import chart_bars_for_range, get_timeframe_spec, normalize_range
from cache.keys import LEVEL_REGIME, make_cache_key
from cache.store import CacheStore, get_cache_store
from core.config import Settings, get_settings
from core.logging import get_logger
from data.access import MarketDataAccess, get_market_data_access
from pipeline.context import InsufficientDataError, build_context
from pipeline.market_pipeline import run_pipeline

logger = get_logger("pipeline.service")


class MarketIntelligenceService:
    def __init__(
        self,
        *,
        dal: MarketDataAccess | None = None,
        cache: CacheStore | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._dal = dal or get_market_data_access()
        self._cache = cache or get_cache_store()
        self._settings = settings or get_settings()

    def compute(
        self,
        symbol_or_id: str | None,
        timeframe: str,
        *,
        historical_range: str | None = None,
        use_cache: bool = True,
    ) -> dict:
        asset = resolve_symbol(symbol_or_id)
        spec = get_timeframe_spec(timeframe)
        range_label = normalize_range(historical_range)
        display_bars = chart_bars_for_range(timeframe, range_label)
        cache_range = f"{spec.yf_period}:{range_label}"

        regime_key = make_cache_key(
            level=LEVEL_REGIME,
            symbol=asset.provider_symbol,
            timeframe=timeframe,
            data_range=cache_range,
        )

        if use_cache:
            cached = self._cache.get_json(regime_key)
            if cached is not None:
                cached.setdefault("meta", {})["cache_hit"] = True
                logger.info(
                    "regime_cache_hit", symbol=asset.provider_symbol, timeframe=timeframe
                )
                return cached

        bars, asset, raw_hit = self._dal.fetch_ohlcv(asset.asset_id, timeframe)
        ctx = build_context(
            asset,
            spec,
            bars,
            display_bars=display_bars,
            historical_range=range_label,
        )
        result = run_pipeline(ctx)
        payload = result.payload
        payload["historical_range"] = range_label
        payload["display_bars"] = display_bars

        if timeframe == "1D":
            payload["correlation"] = self._safe_correlation(payload.get("regime", "UNKNOWN"))

        payload["meta"] = {
            "cache_hit": False,
            "raw_cache_hit": raw_hit,
            "provider": type(self._dal).__name__,
            "diagnostics": result.diagnostics,
        }

        if use_cache:
            self._cache.set_json(
                regime_key, payload, ttl=self._settings.ttl_regime_seconds
            )
        return payload

    def invalidate(self, symbol_or_id: str, timeframe: str) -> None:
        asset = resolve_symbol(symbol_or_id)
        spec = get_timeframe_spec(timeframe)
        for level in ("raw", "feature", "regime"):
            self._cache.invalidate(
                make_cache_key(
                    level=level,
                    symbol=asset.provider_symbol,
                    timeframe=timeframe,
                    data_range=spec.yf_period,
                )
            )

    @staticmethod
    def _safe_correlation(regime_label: str):
        try:
            from engines.correlation_engine import calculate_correlation_intelligence

            return calculate_correlation_intelligence(regime_label=regime_label)
        except Exception as exc:  # correlation is an overlay, never fatal
            logger.warning("correlation_failed", error=str(exc))
            return None

    @property
    def insufficient_data_error(self) -> type[Exception]:
        return InsufficientDataError


_SERVICE: MarketIntelligenceService | None = None


def get_market_intelligence_service() -> MarketIntelligenceService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = MarketIntelligenceService()
    return _SERVICE


def reset_market_intelligence_service() -> None:
    global _SERVICE
    _SERVICE = None
