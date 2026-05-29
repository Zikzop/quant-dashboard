"""
Validation service: run the walk-forward framework against a live asset.

Bridges the DAL (normalized bars) and the engine-shaped frame the framework
expects, then returns a JSON-able OOS report. Reports are cached at the regime
cache level (they are as expensive as a regime fit and equally reproducible
given the same feature version).
"""

from __future__ import annotations

from assets.registry import resolve_symbol
from assets.timeframes import get_timeframe_spec
from cache.keys import make_cache_key
from cache.store import CacheStore, get_cache_store
from core.config import get_settings
from core.logging import get_logger
from data.access import MarketDataAccess, get_market_data_access
from data.providers.utils import to_engine_ohlcv
from validation.framework import ValidationFramework
from validation.walk_forward import WalkForwardSplitter

logger = get_logger("validation.service")


def run_validation(
    symbol_or_id: str | None,
    timeframe: str,
    *,
    n_trials: int = 10,
    use_cache: bool = True,
    dal: MarketDataAccess | None = None,
    cache: CacheStore | None = None,
) -> dict:
    asset = resolve_symbol(symbol_or_id)
    spec = get_timeframe_spec(timeframe)
    dal = dal or get_market_data_access()
    cache = cache or get_cache_store()
    settings = get_settings()

    key = make_cache_key(
        level="validation",
        symbol=asset.provider_symbol,
        timeframe=timeframe,
        data_range=f"{spec.yf_period}:trials{n_trials}",
    )
    if use_cache:
        cached = cache.get_json(key)
        if cached is not None:
            cached.setdefault("meta", {})["cache_hit"] = True
            return cached

    bars, asset, _hit = dal.fetch_ohlcv(asset.asset_id, timeframe)
    engine_df = to_engine_ohlcv(bars)

    n = len(engine_df)
    splitter = WalkForwardSplitter(
        train_size=max(60, n // 4),
        test_size=max(20, n // 12),
        expanding=True,
        purge=1,
        embargo=1,
    )
    framework = ValidationFramework(n_trials=n_trials)
    report = framework.evaluate(
        engine_df,
        engine_name="ema_trend_signal",
        asset=asset.asset_id,
        timeframe=timeframe,
        periods_per_year=spec.bars_per_year,
        splitter=splitter,
    )
    payload = report.to_dict()
    payload["meta"] = {"cache_hit": False}
    if use_cache:
        cache.set_json(key, payload, ttl=settings.ttl_regime_seconds)
    logger.info(
        "validation_complete",
        asset=asset.asset_id,
        timeframe=timeframe,
        n_folds=payload["n_folds"],
        sharpe=payload["oos_metrics"]["sharpe"],
    )
    return payload
