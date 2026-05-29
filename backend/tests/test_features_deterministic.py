"""Deterministic feature + pipeline reproducibility tests (P0.3 acceptance)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from assets.registry import ASSET_REGISTRY
from assets.timeframes import get_timeframe_spec
from features.indicators import compute_indicators, momentum_pct, structure_regime, trend_label
from features.volatility import realized_volatility
from pipeline.context import build_context
from pipeline.market_pipeline import run_pipeline


def test_trend_label_rules():
    assert trend_label(110, 105, 100) == "BULLISH"
    assert trend_label(90, 95, 100) == "BEARISH"
    assert trend_label(100, 95, 100) == "RANGING"


def test_structure_regime_rules():
    assert structure_regime("BULLISH", 6, "CONTRACTING_VOL") == "TRENDING_BULL"
    assert structure_regime("BEARISH", -6, "CONTRACTING_VOL") == "TRENDING_BEAR"
    assert structure_regime("RANGING", 0, "EXPANDING_VOL") == "VOLATILE"
    assert structure_regime("RANGING", 0, "CONTRACTING_VOL") == "RANGING"


def test_momentum_pct_known_value():
    close = pd.Series([100.0] * 20 + [110.0])  # +10% vs 20 bars ago
    assert abs(momentum_pct(close, 20) - 10.0) < 1e-9


def test_indicators_are_pure(synthetic_ohlcv):
    a = compute_indicators(synthetic_ohlcv)
    b = compute_indicators(synthetic_ohlcv)
    assert a.price == b.price and a.ema20 == b.ema20 and a.ema50 == b.ema50
    assert a.trend == b.trend


def test_realized_vol_nonnegative(synthetic_ohlcv):
    rv = realized_volatility(synthetic_ohlcv["Close"], 8766)
    assert rv >= 0.0


def test_pipeline_is_deterministic(synthetic_bars):
    spec = get_timeframe_spec("1H")
    ctx = build_context(ASSET_REGISTRY["BTC"], spec, synthetic_bars)
    p1 = run_pipeline(ctx).payload
    p2 = run_pipeline(ctx).payload
    dump = lambda p: json.dumps(p, sort_keys=True, default=str)
    assert dump(p1) == dump(p2)


def test_pipeline_payload_has_core_fields(synthetic_bars):
    spec = get_timeframe_spec("1H")
    ctx = build_context(ASSET_REGISTRY["BTC"], spec, synthetic_bars)
    payload = run_pipeline(ctx).payload
    for key in [
        "symbol", "asset_id", "timeframe", "feature_version", "price", "trend",
        "market_state", "regime", "signal", "garch_vol", "regime_transition", "chart_data",
    ]:
        assert key in payload, f"missing {key}"
    assert payload["chart_data"], "chart_data should not be empty"
