"""
Z-score mean reversion alpha with stationarity pre-checks.

Disabled or down-weighted when Hurst/ADF suggest trending behavior.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import (
    causal_trend_regime,
    causal_vol_regime,
    is_trending_regime,
    regime_confidence,
)
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata
from statistical_testing.stationarity_tests import estimate_hurst_exponent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ZScoreReversionConfig:
    zscore_entry: float = 2.0
    hurst_window: int = 100
    min_periods: int = 20


class ZScoreReversionAlpha(AlphaBase):
    """Probabilistic reversion from z-score extremes with stationarity gating."""

    def __init__(self, config: ZScoreReversionConfig | None = None) -> None:
        self.config = config or ZScoreReversionConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="zscore_reversion",
                description=(
                    "Fades statistically extreme z-score moves expecting partial reversion "
                    "to rolling mean. Requires approximate stationarity locally."
                ),
                assumptions=(
                    "Price oscillates around slow-moving mean over horizon.",
                    "Z-score computed on backward-looking window only.",
                ),
                failure_modes=(
                    "Trending markets: reversion signals become counter-trend traps.",
                    "Structural breaks invalidate mean level.",
                    "Volatility regime shifts widen bands suddenly.",
                ),
                regime_dependency=("RANGE", "MEAN_REVERT", "LOW_VOL"),
                holding_period="short",
                required_features=("close", "z_score", "rolling_volatility", "log_return"),
                expected_behavior="Negative score on high z (fade overbought); positive on low z.",
                family="mean_reversion",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config
        z = df["z_score"]
        reversion_raw = -z / cfg.zscore_entry
        alpha_score = reversion_raw.apply(lambda x: self.sigmoid_score(x, scale=1.0))

        trend = causal_trend_regime(df["close"])
        vol_reg = causal_vol_regime(df["log_return"])
        trending = is_trending_regime(trend)

        global_hurst = estimate_hurst_exponent(df["log_return"].dropna())
        hurst_hint = pd.Series(global_hurst.regime_hint, index=df.index)
        stationarity_gate = pd.Series(1.0, index=df.index)
        if global_hurst.regime_hint == "trending":
            stationarity_gate *= 0.3
        elif global_hurst.regime_hint == "mean_reverting":
            stationarity_gate *= 1.0

        gate = stationarity_gate * (~trending).astype(float)
        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg) * gate * (z.abs() / cfg.zscore_entry).clip(0, 1) * 0.5 + 0.1
        )

        alpha_score = alpha_score * gate

        warnings: list[str] = []
        if trending.mean() > 0.5:
            warnings.append("Majority trending regime — mean reversion heavily penalized.")

        vol = df["rolling_volatility"].replace(0, np.nan)
        exp_mean = reversion_raw * 0.002
        exp_std = vol.fillna(vol.median())
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=hurst_hint,
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(-0.3, index=df.index),
            distribution_interpretation=pd.Series(
                "Mean-reversion tilt; disabled under trend regimes.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"z_score": z, "stationarity_gate": gate},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=tuple(warnings))
