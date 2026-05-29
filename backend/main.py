"""
FastAPI application — thin HTTP layer.

All market intelligence now flows through the layered backend:

    HTTP (this file)
      -> MarketIntelligenceService   (orchestration + regime cache)
        -> MarketDataAccess          (provider + reliability + raw cache + validation)
        -> deterministic pipeline    (features -> volatility -> regimes -> signals)

This module owns nothing but request handling: routing, request-ID propagation,
latency metrics, and translating domain errors into HTTP responses. The payload
shape is unchanged from the prototype (backward compatible) with additive fields
(``asset_id``, ``feature_version``, ``regime_transition``, ``meta``).
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from assets.registry import list_asset_metadata
from assets.timeframes import (
    CANONICAL_TIMEFRAMES,
    DEFAULT_HISTORICAL_RANGE,
    HISTORICAL_RANGES,
    VALID_TIMEFRAMES,
    normalize_range,
)
from core.config import get_settings
from core.logging import (
    clear_request_id,
    configure_logging,
    get_logger,
    set_request_id,
)
from core.metrics import API_LATENCY, render_latest
from pipeline.context import InsufficientDataError
from pipeline.service import get_market_intelligence_service
from schemas.market import MarketPayload
from validation.service import run_validation

settings = get_settings()
configure_logging(level=settings.log_level, json_output=settings.log_json)
logger = get_logger("api")

app = FastAPI(title="Quant Regime Research API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_TIMEFRAME = "1D"


@app.middleware("http")
async def request_context(request: Request, call_next):
    """Bind a request id, time the request, and surface the id to clients."""
    rid = set_request_id(request.headers.get("X-Request-ID"))
    start = time.perf_counter()
    status = "500"
    try:
        response: Response = await call_next(request)
        status = str(response.status_code)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        elapsed = time.perf_counter() - start
        API_LATENCY.labels(
            endpoint=request.url.path,
            asset=request.query_params.get("symbol", "-"),
            timeframe=request.path_params.get("tf", "-") if hasattr(request, "path_params") else "-",
            status=status,
        ).observe(elapsed)
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=status,
            duration_ms=round(elapsed * 1000, 1),
        )
        clear_request_id()


def _serialize(payload: dict) -> dict:
    """Enforce the response contract; fall back to raw payload on drift.

    Validating through ``MarketPayload`` guarantees the documented shape. If the
    pipeline ever emits something off-contract we log loudly but still serve the
    request (availability over strictness for a read-only research endpoint).
    """
    try:
        return MarketPayload.model_validate(payload).model_dump(mode="json")
    except Exception as exc:
        logger.error("payload_contract_violation", error=str(exc))
        return payload


# ─────────────────────────────────────────────────────────────────────────────
# Operational endpoints
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": settings.market_data_provider,
        "feature_version": settings.feature_version,
        "timeframes": list(CANONICAL_TIMEFRAMES),
        "historical_ranges": list(HISTORICAL_RANGES),
    }


@app.get("/metrics")
def metrics():
    payload, content_type = render_latest()
    return PlainTextResponse(content=payload, media_type=content_type)


@app.get("/assets")
def assets():
    return {
        "assets": list_asset_metadata(),
        "timeframes": list(CANONICAL_TIMEFRAMES),
        "historical_ranges": list(HISTORICAL_RANGES),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Market intelligence
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/market")
def get_market(symbol: str = "BTC", range: str = DEFAULT_HISTORICAL_RANGE):
    """Legacy daily endpoint — now multi-asset and routed through the pipeline."""
    try:
        range_label = normalize_range(range)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    return _market(symbol, DEFAULT_TIMEFRAME, range_label)


@app.get("/market/timeframe/{tf}")
def get_market_timeframe(
    tf: str,
    symbol: str = "BTC",
    range: str = DEFAULT_HISTORICAL_RANGE,
):
    if tf not in VALID_TIMEFRAMES:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid timeframe: {tf}. Valid: {sorted(VALID_TIMEFRAMES)}"},
        )
    try:
        range_label = normalize_range(range)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    return _market(symbol, tf, range_label)


def _market(symbol: str, tf: str, historical_range: str = DEFAULT_HISTORICAL_RANGE):
    service = get_market_intelligence_service()
    try:
        payload = service.compute(symbol, tf, historical_range=historical_range)
        return _serialize(payload)
    except InsufficientDataError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})
    except ValueError as exc:  # unknown symbol / timeframe
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:
        logger.exception("market_request_failed", symbol=symbol, timeframe=tf)
        return JSONResponse(status_code=502, content={"error": str(exc)})


@app.get("/correlation")
def get_correlation():
    from engines.correlation_engine import calculate_correlation_intelligence

    try:
        return calculate_correlation_intelligence()
    except Exception as exc:
        logger.exception("correlation_failed")
        return JSONResponse(status_code=502, content={"error": str(exc)})


# ─────────────────────────────────────────────────────────────────────────────
# Validation (P0.5)
# ─────────────────────────────────────────────────────────────────────────────


@app.get("/validation/{tf}")
def get_validation(tf: str, symbol: str = "BTC", n_trials: int = 10):
    if tf not in VALID_TIMEFRAMES:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid timeframe: {tf}. Valid: {sorted(VALID_TIMEFRAMES)}"},
        )
    try:
        return run_validation(symbol, tf, n_trials=max(1, n_trials))
    except InsufficientDataError as exc:
        return JSONResponse(status_code=422, content={"error": str(exc)})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    except Exception as exc:
        logger.exception("validation_failed", symbol=symbol, timeframe=tf)
        return JSONResponse(status_code=502, content={"error": str(exc)})


# ─────────────────────────────────────────────────────────────────────────────
# Cache administration
# ─────────────────────────────────────────────────────────────────────────────


@app.post("/admin/cache/invalidate")
def invalidate_cache(symbol: str = "BTC", timeframe: str = DEFAULT_TIMEFRAME):
    if timeframe not in VALID_TIMEFRAMES:
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid timeframe: {timeframe}"},
        )
    service = get_market_intelligence_service()
    service.invalidate(symbol, timeframe)
    return {"status": "invalidated", "symbol": symbol, "timeframe": timeframe}
