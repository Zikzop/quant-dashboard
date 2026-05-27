"""
Regime transition alpha — edge around causal regime label changes.

Inefficiency rationale: slow regime recognition by discretionary participants.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata


@dataclass(frozen=True)
class RegimeTransitionConfig:
    transition_penalty: float = 0.5


class RegimeTransitionAlpha(AlphaBase):
    """Probabilistic signal on trend/vol regime transitions."""

    def __init__(self, config: RegimeTransitionConfig | None = None) -> None:
        self.config = config or RegimeTransitionConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="regime_transition",
                description=(
                    "Captures short-horizon edge when causal regime labels transition. "
                    "Behavioral: delayed adaptation to new market state."
                ),
                assumptions=(
                    "Regime labels stable enough to detect transitions.",
                    "Transitions contain information not fully priced.",
                ),
                failure_modes=(
                    "Whipsaw in choppy boundary regimes.",
                    "Transition frequency too high (overtrading).",
                    "Regime classifier lag causes late entry.",
                ),
                regime_dependency=("TRANSITION", "TREND_CHANGE", "VOL_SHIFT"),
                holding_period="short",
                required_features=("close", "log_return", "rolling_volatility"),
                expected_behavior="Elevated score immediately post transition.",
                family="inefficiency",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        trend = causal_trend_regime(df["close"])
        vol_reg = causal_vol_regime(df["log_return"])

        trend_chg = (trend != trend.shift(1)).astype(float)
        vol_chg = (vol_reg != vol_reg.shift(1)).astype(float)
        transition = ((trend_chg + vol_chg) / 2).clip(0, 1)

        mom = df["log_return"].rolling(5, min_periods=3).sum()
        raw = mom * transition
        alpha_score = raw.apply(lambda x: self.sigmoid_score(x, scale=0.02))

        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg) * transition * 0.5
            + (1 - transition) * self.config.transition_penalty * 0.1
        )

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
            stationarity_hint=pd.Series("transition", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.3, index=df.index),
            distribution_interpretation=pd.Series(
                "Transition inefficiency; decays rapidly post adaptation.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"transition_intensity": transition, "momentum": mom},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=())
