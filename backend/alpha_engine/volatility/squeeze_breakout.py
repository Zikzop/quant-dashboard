"""
Squeeze breakout alpha — joint compression + directional pressure probability.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata


@dataclass(frozen=True)
class SqueezeBreakoutConfig:
    compression_window: int = 20
    pressure_window: int = 10
    min_periods: int | None = None


class SqueezeBreakoutAlpha(AlphaBase):
    """
    Combines vol compression with directional pressure for breakout likelihood.

    NOT a binary breakout indicator — outputs probabilistic combined score.
    """

    def __init__(self, config: SqueezeBreakoutConfig | None = None) -> None:
        self.config = config or SqueezeBreakoutConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="squeeze_breakout",
                description=(
                    "Models joint probability of compression release with directional "
                    "pressure. Behavioral: pent-up positioning resolves on range exit."
                ),
                assumptions=(
                    "Compression and pressure independently measurable causally.",
                    "Breakout follows sufficient compression duration.",
                ),
                failure_modes=(
                    "False squeeze: vol stays compressed indefinitely.",
                    "Directional pressure reverses before release.",
                ),
                regime_dependency=("COMPRESSED", "LOW_VOL", "TRANSITION"),
                holding_period="short",
                required_features=("atr", "rolling_volatility", "close", "log_return", "z_score"),
                expected_behavior="Elevated score when compressed + directional pressure.",
                family="volatility",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config
        min_p = cfg.min_periods or cfg.compression_window

        vol = df["rolling_volatility"]
        vol_short = vol.rolling(cfg.compression_window, min_periods=min_p).mean()
        vol_long = vol.rolling(cfg.compression_window * 3, min_periods=min_p * 2).mean()
        compression = (1 - (vol_short / vol_long.replace(0, np.nan))).clip(0, 1)

        pressure = df["log_return"].rolling(cfg.pressure_window, min_periods=3).sum()
        pressure_norm = pressure / vol.replace(0, np.nan)

        squeeze_score = compression * pressure_norm.abs()
        direction = np.sign(pressure_norm)
        raw = squeeze_score * direction
        alpha_score = raw.apply(lambda x: self.sigmoid_score(x, scale=0.3))

        trend = causal_trend_regime(df["close"])
        vol_reg = causal_vol_regime(df["log_return"])
        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg) * squeeze_score.clip(0, 1) * 0.55 + 0.15
        )

        exp_std = vol.fillna(vol.median())
        exp_mean = raw.fillna(0) * 0.002
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("squeeze", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.4, index=df.index),
            distribution_interpretation=pd.Series(
                "Squeeze release with directional bias; fat tails on breakout.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={
                "compression": compression,
                "pressure": pressure_norm,
                "squeeze_score": squeeze_score,
            },
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=())
