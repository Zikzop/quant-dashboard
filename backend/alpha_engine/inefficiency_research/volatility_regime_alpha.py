"""
Volatility regime alpha — structural edge from vol regime persistence and shifts.

Inefficiency rationale: vol risk premium and hedging demand cycles.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata


@dataclass(frozen=True)
class VolRegimeAlphaConfig:
    persistence_window: int = 10


class VolatilityRegimeAlpha(AlphaBase):
    """Alpha from vol regime state and persistence."""

    def __init__(self, config: VolRegimeAlphaConfig | None = None) -> None:
        self.config = config or VolRegimeAlphaConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="volatility_regime",
                description=(
                    "Exploits vol regime persistence and risk premium dynamics. "
                    "Structural: dealer gamma, vol selling/buying flows."
                ),
                assumptions=(
                    "Vol regimes cluster beyond i.i.d. assumption.",
                    "HIGH_VOL periods carry risk premium compensation.",
                ),
                failure_modes=(
                    "Central bank intervention suppresses vol artificially.",
                    "Regime duration exceeds model calibration.",
                ),
                regime_dependency=("HIGH_VOL", "LOW_VOL", "EXPANDING_VOL"),
                holding_period="medium",
                required_features=("rolling_volatility", "realized_volatility", "log_return", "close"),
                expected_behavior="Score reflects vol regime tilt and persistence.",
                family="inefficiency",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        vol_reg = causal_vol_regime(df["log_return"])
        trend = causal_trend_regime(df["close"])

        high_vol = (vol_reg == "HIGH_VOL").astype(float)
        persistence = high_vol.rolling(
            self.config.persistence_window, min_periods=3
        ).mean()

        vol_slope = df["rolling_volatility"].diff(5) / 5
        raw = persistence * np.sign(vol_slope) + (high_vol - 0.5) * 0.5
        alpha_score = raw.apply(lambda x: self.sigmoid_score(x, scale=0.3))

        conf = self.clip_confidence(regime_confidence(trend, vol_reg) * 0.6 + 0.2)

        vol = df["rolling_volatility"].replace(0, np.nan)
        exp_mean = raw.fillna(0) * 0.001
        exp_std = vol.fillna(vol.median())
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("vol_regime", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.6, index=df.index),
            distribution_interpretation=pd.Series(
                "Vol regime risk premium; unsigned vol exposure component.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"vol_persistence": persistence, "high_vol_flag": high_vol},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=())
