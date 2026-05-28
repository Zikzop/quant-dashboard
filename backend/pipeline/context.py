"""
Pipeline context and result containers.

``PipelineContext`` is the immutable input to the pipeline: a resolved asset, a
timeframe spec, and the normalized bars. ``build_context`` performs the
``normalization`` stage (flat provider frame -> title-case engine frame with a
UTC DatetimeIndex) so every downstream stage sees one canonical shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from assets.registry import AssetDefinition
from assets.timeframes import TimeframeSpec
from core.config import FEATURE_VERSION
from data.providers.utils import to_engine_ohlcv

# Engines need enough bars for stable smoothing / fitting.
MIN_BARS = 30


class InsufficientDataError(ValueError):
    """Raised when there are too few bars to compute stable features."""


@dataclass(frozen=True)
class PipelineContext:
    asset: AssetDefinition
    timeframe: str
    spec: TimeframeSpec
    bars: pd.DataFrame          # flat normalized schema (unified)
    engine_df: pd.DataFrame     # title-case OHLCV, UTC DatetimeIndex
    feature_version: str = FEATURE_VERSION


@dataclass
class PipelineResult:
    """All stage outputs plus the serialized payload."""

    payload: dict[str, Any] = field(default_factory=dict)
    chart_data: list[dict] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def build_context(
    asset: AssetDefinition,
    spec: TimeframeSpec,
    bars: pd.DataFrame,
) -> PipelineContext:
    if bars is None or bars.empty:
        raise InsufficientDataError(
            f"No data for {asset.provider_symbol} @ {spec.timeframe}"
        )
    engine_df = to_engine_ohlcv(bars)
    if len(engine_df) < MIN_BARS:
        raise InsufficientDataError(
            f"Insufficient data for {spec.timeframe}: {len(engine_df)} bars (<{MIN_BARS})"
        )
    return PipelineContext(
        asset=asset,
        timeframe=spec.timeframe,
        spec=spec,
        bars=bars,
        engine_df=engine_df,
    )
