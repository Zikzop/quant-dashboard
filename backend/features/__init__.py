"""
Deterministic feature functions.

Each function is a pure transformation: identical input OHLCV always yields
identical output (HMM/GARCH use fixed seeds and full-sample MLE, so they are
reproducible too). Features carry no hidden state and never fetch data — they
receive a normalized engine frame and return typed structures. This is what
makes the pipeline stage-by-stage testable and the cache safe.
"""

from features.indicators import (
    IndicatorFeatures,
    compute_indicators,
    ema,
    momentum_pct,
    structure_regime,
    trend_label,
)
from features.regimes import (
    AdxFeatures,
    HmmFeatures,
    compute_adx,
    compute_hmm,
)
from features.volatility import (
    GarchFeatures,
    compute_garch,
    realized_volatility,
)

__all__ = [
    "IndicatorFeatures",
    "compute_indicators",
    "ema",
    "momentum_pct",
    "structure_regime",
    "trend_label",
    "AdxFeatures",
    "HmmFeatures",
    "compute_adx",
    "compute_hmm",
    "GarchFeatures",
    "compute_garch",
    "realized_volatility",
]
