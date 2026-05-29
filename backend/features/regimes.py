"""
Regime features (ADX + HMM).

Wraps the existing ADX and HMM engines with: fit-duration / failure metrics,
graceful degradation, and typed outputs. The HMM is single-fit for the chart
overlay (fast, full-history posterior) and expanding-window for the latest-bar
snapshot (causal) — exactly as the prototype did, but isolated and observable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

import pandas as pd

from core.logging import get_logger
from core.metrics import record_fit_failure, time_fit
from engines.adx_engine import ADXRegimeEngine, adx_result_to_dict

logger = get_logger("features.regimes")

_MAX_HMM_BARS = 2000


@dataclass(frozen=True)
class AdxFeatures:
    latest: Dict
    series: pd.DataFrame


@dataclass(frozen=True)
class HmmFeatures:
    snapshot: Dict
    history: pd.DataFrame = field(default_factory=pd.DataFrame)


def compute_adx(engine_df: pd.DataFrame, adx_engine: ADXRegimeEngine) -> AdxFeatures:
    series = adx_engine.compute_per_bar_series(engine_df)
    latest = adx_result_to_dict(adx_engine.compute_latest(engine_df))
    return AdxFeatures(latest=latest, series=series)


_HMM_NEUTRAL = {
    "regime_label": "UNKNOWN",
    "trend_probability": 0.0,
    "crisis_probability": 0.0,
    "mean_revert_probability": 0.0,
}


def compute_hmm(engine_df: pd.DataFrame, hmm_engine, timeframe: str) -> HmmFeatures:
    sample = engine_df.iloc[-_MAX_HMM_BARS:] if len(engine_df) > _MAX_HMM_BARS else engine_df
    try:
        with time_fit("hmm", timeframe):
            history = hmm_engine.compute_single_fit_regimes(sample)
            snapshot = hmm_engine.classify_regimes(sample)
        return HmmFeatures(snapshot=snapshot, history=history)
    except Exception as exc:
        record_fit_failure("hmm")
        logger.warning("hmm_fit_failed", timeframe=timeframe, error=str(exc))
        return HmmFeatures(snapshot=dict(_HMM_NEUTRAL), history=pd.DataFrame())
