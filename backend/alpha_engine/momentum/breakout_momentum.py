"""
Breakout momentum alpha — probabilistic strength of range expansion.

Models likelihood of continuation after causal range breakout, not binary signals.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata


@dataclass(frozen=True)
class BreakoutMomentumConfig:
    range_window: int = 20
    breakout_threshold: float = 0.5
    min_periods: int | None = None


class BreakoutMomentumAlpha(AlphaBase):
    """Range breakout strength with probabilistic continuation score."""

    def __init__(self, config: BreakoutMomentumConfig | None = None) -> None:
        self.config = config or BreakoutMomentumConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="breakout_momentum",
                description=(
                    "Captures momentum following range expansion when price exits "
                    "backward-looking bounds. Rationale: stop-run dynamics and "
                    "delayed institutional participation."
                ),
                assumptions=(
                    "Breakouts defined on past range only (no future highs/lows).",
                    "Volatility expansion often accompanies valid breakouts.",
                ),
                failure_modes=(
                    "False breakouts in mean-reverting regimes.",
                    "Low liquidity causes spurious range pierces.",
                    "Overnight gap distorts range definition.",
                ),
                regime_dependency=("UPTREND", "HIGH_VOL", "EXPANSION"),
                holding_period="short",
                required_features=("close", "high", "low", "atr", "rolling_volatility"),
                expected_behavior="Elevated score after confirmed upward range exit.",
                family="momentum",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config
        min_p = cfg.min_periods or cfg.range_window

        close = df["close"]
        high_roll = df["high"].rolling(cfg.range_window, min_periods=min_p).max().shift(1)
        low_roll = df["low"].rolling(cfg.range_window, min_periods=min_p).min().shift(1)
        range_width = (high_roll - low_roll).replace(0, np.nan)

        up_break = (close - high_roll) / range_width
        down_break = (low_roll - close) / range_width
        breakout_raw = up_break.fillna(0) - down_break.fillna(0)

        vol_ratio = df["atr"] / df["rolling_volatility"].replace(0, np.nan)
        raw = breakout_raw * vol_ratio.clip(0, 3)
        alpha_score = raw.apply(lambda x: self.sigmoid_score(x, scale=cfg.breakout_threshold))

        trend = causal_trend_regime(close)
        vol_reg = causal_vol_regime(close.pct_change())
        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg) * (breakout_raw.abs() > 0).astype(float) * 0.6 + 0.2
        )

        exp_std = df["rolling_volatility"].fillna(df["rolling_volatility"].median())
        exp_mean = breakout_raw * 0.005
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("breakout", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.5, index=df.index),
            distribution_interpretation=pd.Series(
                "Breakout continuation; positive skew on upside breaks.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"breakout_raw": breakout_raw, "vol_ratio": vol_ratio},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=())
