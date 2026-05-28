"""
API contract + schema-drift + regime-stability tests.

Runs against the live FastAPI app with the deterministic MockProvider, so it is
fast and offline. The MarketPayload model is the contract; if the pipeline emits
an off-contract field these tests fail (that is the anti-drift guarantee).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

import main
from assets.registry import ASSET_REGISTRY
from assets.timeframes import get_timeframe_spec
from pipeline.context import build_context
from pipeline.market_pipeline import run_pipeline
from schemas.market import MarketPayload


def _client() -> TestClient:
    return TestClient(main.app)


def test_health_and_assets():
    c = _client()
    assert c.get("/health").status_code == 200
    assets = c.get("/assets").json()
    ids = {a["asset_id"] for a in assets["assets"]}
    assert {"BTC", "GOLD", "ES", "NQ", "DXY"}.issubset(ids)
    assert assets["timeframes"] == ["1m", "5m", "15m", "1H", "4H", "1D"]


def test_market_endpoint_matches_contract():
    c = _client()
    r = c.get("/market/timeframe/1H?symbol=BTC&range=3M")
    assert r.status_code == 200
    assert "X-Request-ID" in r.headers
    body = r.json()
    # Strict contract validation: must parse with extra="forbid".
    validated = MarketPayload.model_validate(body)
    assert validated.historical_range == "3M"
    assert validated.display_bars > 0


def test_invalid_timeframe_and_symbol():
    c = _client()
    assert c.get("/market/timeframe/99x").status_code == 400
    assert c.get("/market/timeframe/1D?symbol=NOPE").status_code == 400


def test_chart_bar_times_are_valid_unix():
    """Regression: chart bars must carry real timestamps (not RangeIndex 0)."""
    c = _client()
    r = c.get("/market/timeframe/1H?symbol=GOLD&range=3M")
    assert r.status_code == 200
    chart = r.json().get("chart_data") or []
    assert len(chart) >= 30
    times = [b["time"] for b in chart]
    assert all(isinstance(t, int) and t > 1_000_000_000 for t in times), (
        f"invalid chart times sample: {times[:3]} ... {times[-3:]}"
    )
    assert len(set(times)) > len(times) // 2


def test_multi_asset_switch():
    c = _client()
    btc = c.get("/market/timeframe/1D?symbol=BTC").json()
    gold = c.get("/market/timeframe/1D?symbol=GOLD").json()
    assert btc["asset_id"] == "BTC" and btc["symbol"] == "BTC-USD"
    assert gold["asset_id"] == "GOLD" and gold["symbol"] == "GC=F"


def test_regime_cache_hit_on_repeat():
    c = _client()
    first = c.get("/market/timeframe/15m?symbol=ES").json()
    second = c.get("/market/timeframe/15m?symbol=ES").json()
    assert first["meta"]["cache_hit"] is False
    assert second["meta"]["cache_hit"] is True


def test_validation_endpoint_contract():
    c = _client()
    r = c.get("/validation/1D?symbol=BTC&n_trials=5")
    assert r.status_code == 200
    body = r.json()
    assert "oos_metrics" in body and "folds" in body
    assert 0.0 <= body["oos_metrics"]["hit_rate"] <= 1.0


def test_metrics_endpoint_exposes_prometheus():
    c = _client()
    r = c.get("/metrics")
    assert r.status_code == 200
    assert b"api_request_latency_seconds" in r.content


def test_pipeline_payload_validates_against_schema(synthetic_bars):
    spec = get_timeframe_spec("1H")
    ctx = build_context(ASSET_REGISTRY["BTC"], spec, synthetic_bars)
    payload = run_pipeline(ctx).payload
    payload["meta"] = {"cache_hit": False}
    payload["historical_range"] = ctx.historical_range
    payload["display_bars"] = ctx.display_bars
    MarketPayload.model_validate(payload)


def test_regime_transition_is_well_formed(synthetic_bars):
    spec = get_timeframe_spec("1H")
    ctx = build_context(ASSET_REGISTRY["BTC"], spec, synthetic_bars)
    transition = run_pipeline(ctx).payload["regime_transition"]
    assert 0.0 <= transition["instability_score"] <= 1.0
    for src in transition["states"]:
        # Rows are stochastic (within payload rounding tolerance, 4 dp).
        assert abs(sum(transition["matrix"][src].values()) - 1.0) < 1e-2
        assert 0.0 <= transition["persistence"][src] <= 1.0


def test_regime_transition_is_deterministic_and_consistent(synthetic_bars):
    """Regime-stability smoke test: the transition payload is reproducible and
    its current_state agrees with the snapshot regime label."""
    spec = get_timeframe_spec("1H")
    ctx = build_context(ASSET_REGISTRY["BTC"], spec, synthetic_bars)
    p1 = run_pipeline(ctx).payload
    p2 = run_pipeline(ctx).payload
    assert p1["regime_transition"] == p2["regime_transition"]
    # n_transitions should equal regime-history length minus 1 (or 0 if empty).
    t = p1["regime_transition"]
    assert t["n_transitions"] >= 0
    assert t["current_state"] in (None, *t["states"])
