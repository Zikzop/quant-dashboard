"""
Shared causal regime utilities for alpha engine modules.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from feature_analysis.regime_feature_analysis import (
    classify_trend_regime,
    classify_volatility_regime,
)


def causal_trend_regime(close: pd.Series, *, window: int = 50) -> pd.Series:
    return classify_trend_regime(close, window=window)


def causal_vol_regime(returns: pd.Series, *, window: int = 20) -> pd.Series:
    return classify_volatility_regime(returns, window=window)


def regime_confidence(
    trend: pd.Series,
    vol: pd.Series,
    *,
    persistence: pd.Series | None = None,
) -> pd.Series:
    """Heuristic confidence from regime label stability (backward-looking)."""
    trend_stable = (trend == trend.shift(1)).astype(float)
    vol_stable = (vol == vol.shift(1)).astype(float)
    base = (trend_stable + vol_stable) / 2.0
    if persistence is not None:
        base = (base + persistence.clip(0, 1)) / 2.0
    return base.fillna(0.5)


def is_trending_regime(trend: pd.Series) -> pd.Series:
    return trend.isin(["UPTREND", "DOWNTREND"])


def is_compressed_vol(vol: pd.Series) -> pd.Series:
    return vol == "LOW_VOL"
