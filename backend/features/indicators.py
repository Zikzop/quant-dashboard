"""
Price-structure indicators (pure, deterministic).

These intentionally reproduce the exact math the prototype used inline in
``main.py`` (EMA20/50, EMA-stack trend, 20-bar momentum, structure regime), but
as isolated, typed, individually testable functions. Keeping the math identical
preserves backward compatibility of the API payload.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class IndicatorFeatures:
    price: float
    ema20: float
    ema50: float
    trend: str
    momentum: float
    ema20_series: pd.Series
    ema50_series: pd.Series


def ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span).mean()


def trend_label(price: float, ema20: float, ema50: float) -> str:
    if price > ema20 and ema20 > ema50:
        return "BULLISH"
    if price < ema20 and ema20 < ema50:
        return "BEARISH"
    return "RANGING"


def momentum_pct(close: pd.Series, lookback: int = 20) -> float:
    n = len(close)
    if n < 2:
        return 0.0
    eff_lookback = min(lookback, n - 1)
    prior = float(close.iloc[-eff_lookback - 1])
    if prior == 0:
        return 0.0
    return ((float(close.iloc[-1]) / prior) - 1) * 100


def structure_regime(trend: str, momentum: float, vol_regime: str) -> str:
    regime = "RANGING"
    if vol_regime == "EXPANDING_VOL":
        regime = "VOLATILE"
    if trend == "BULLISH" and momentum > 5:
        regime = "TRENDING_BULL"
    elif trend == "BEARISH" and momentum < -5:
        regime = "TRENDING_BEAR"
    return regime


def compute_indicators(engine_df: pd.DataFrame) -> IndicatorFeatures:
    """Compute the indicator stage from a title-case engine OHLCV frame."""
    close = engine_df["Close"].astype(float)
    ema20_series = ema(close, 20)
    ema50_series = ema(close, 50)

    price = float(close.iloc[-1])
    ema20 = float(ema20_series.iloc[-1])
    ema50 = float(ema50_series.iloc[-1])

    return IndicatorFeatures(
        price=price,
        ema20=ema20,
        ema50=ema50,
        trend=trend_label(price, ema20, ema50),
        momentum=momentum_pct(close),
        ema20_series=ema20_series,
        ema50_series=ema50_series,
    )
