"""
Volatility expansion alpha — probabilistic likelihood of vol regime shift upward.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata


@dataclass(frozen=True)
class VolExpansionConfig:
    vol_window: int = 20
    slope_window: int = 10
    min_periods: int | None = None


class VolatilityExpansionAlpha(AlphaBase):
    """Detects rising realized vol with probabilistic expansion score."""

    def __init__(self, config: VolExpansionConfig | None = None) -> None:
        self.config = config or VolExpansionConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="volatility_expansion",
                description=(
                    "Models probability of volatility expansion from rising vol slope "
                    "and clustering. Rationale: vol feedback loops and risk-off flows."
                ),
                assumptions=(
                    "Realized vol slope computed on past data only.",
                    "Expansion often precedes large absolute returns (unsigned).",
                ),
                failure_modes=(
                    "False expansion signals in seasonal vol patterns.",
                    "Single shock mean-reverts quickly (false positive).",
                ),
                regime_dependency=("EXPANDING_VOL", "HIGH_VOL", "TRANSITION"),
                holding_period="short",
                required_features=("rolling_volatility", "realized_volatility", "log_return", "close"),
                expected_behavior="High score when vol slope positive and accelerating.",
                family="volatility",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config
        min_p = cfg.min_periods or cfg.vol_window

        vol = df["rolling_volatility"]
        vol_slope = vol.diff(cfg.slope_window) / cfg.slope_window
        vol_accel = vol_slope.diff(cfg.slope_window)
        sq_ret = df["log_return"] ** 2
        clustering = sq_ret.rolling(cfg.vol_window, min_periods=min_p).mean()

        raw = (vol_slope / vol.replace(0, np.nan) + vol_accel * 10).replace(
            [np.inf, -np.inf], np.nan
        )
        expansion_prob = raw.apply(lambda x: self.sigmoid_score(x, scale=0.05))
        alpha_score = expansion_prob * np.sign(df["log_return"].rolling(5, min_periods=3).sum())

        trend = causal_trend_regime(df["close"])
        vol_reg = causal_vol_regime(df["log_return"])
        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg) * expansion_prob.abs() * 0.6 + 0.15
        )

        exp_std = vol.fillna(vol.median())
        exp_mean = expansion_prob * 0.003
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("vol_expansion", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.8, index=df.index),
            distribution_interpretation=pd.Series(
                "Expansion likelihood; unsigned vol rise with directional tilt.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={
                "vol_slope": vol_slope,
                "clustering": clustering,
                "expansion_prob": expansion_prob,
            },
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=())
