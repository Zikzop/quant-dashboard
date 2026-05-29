"""
Volatility features (realized + GARCH).

Wraps the existing GARCH engine but adds: timeframe-correct annualization,
fit-duration metrics, and graceful failure (a GARCH MLE non-convergence must
degrade to a neutral, well-typed result, never 500 the request).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.logging import get_logger
from core.metrics import record_fit_failure, time_fit
from engines.garch_engine import calculate_garch_volatility_series

logger = get_logger("features.volatility")

# Cap the GARCH estimation window: MLE cost grows with sample length and the
# conditional-vol recursion is dominated by recent observations anyway.
_MAX_GARCH_BARS = 2000


@dataclass(frozen=True)
class GarchFeatures:
    garch_vol: float
    vol_regime: str
    vol_slope: float
    series: pd.DataFrame  # index-aligned garch_vol / vol_slope / vol_regime


def realized_volatility(close: pd.Series, bars_per_year: int) -> float:
    """Annualized realized volatility for the timeframe."""
    returns = close.pct_change()
    std = returns.std()
    if pd.isna(std):
        return 0.0
    return float(std * np.sqrt(bars_per_year))


def compute_garch(close: pd.Series, timeframe: str) -> GarchFeatures:
    sample = close.iloc[-_MAX_GARCH_BARS:] if len(close) > _MAX_GARCH_BARS else close
    empty = pd.DataFrame(
        columns=["garch_vol", "vol_slope", "vol_regime"], index=close.index
    )
    try:
        with time_fit("garch", timeframe):
            series = calculate_garch_volatility_series(sample)
        valid = series.dropna(subset=["garch_vol"])
        if valid.empty:
            raise ValueError("GARCH produced no finite conditional volatility")
        latest = valid.iloc[-1]
        return GarchFeatures(
            garch_vol=round(float(latest["garch_vol"]), 2),
            vol_regime=str(latest["vol_regime"]),
            vol_slope=round(float(latest["vol_slope"]), 2)
            if not pd.isna(latest["vol_slope"])
            else 0.0,
            series=series.reindex(close.index),
        )
    except Exception as exc:
        record_fit_failure("garch")
        logger.warning("garch_fit_failed", timeframe=timeframe, error=str(exc))
        return GarchFeatures(
            garch_vol=0.0, vol_regime="UNKNOWN", vol_slope=0.0, series=empty
        )
