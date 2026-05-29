"""
Deterministic market-intelligence pipeline (live path).

Distinct from the offline ``pipelines/`` package (which builds parquet tiers).
This package turns a normalized OHLCV frame into the full regime/signal payload
through explicit, individually-testable stages:

    raw_data -> normalization -> indicators -> volatility
             -> regime_inference -> signal_generation -> overlays

Given identical input bars, the pipeline produces identical output.
"""

from pipeline.context import PipelineContext, PipelineResult, build_context
from pipeline.market_pipeline import run_pipeline
from pipeline.service import MarketIntelligenceService, get_market_intelligence_service

__all__ = [
    "PipelineContext",
    "PipelineResult",
    "build_context",
    "run_pipeline",
    "MarketIntelligenceService",
    "get_market_intelligence_service",
]
