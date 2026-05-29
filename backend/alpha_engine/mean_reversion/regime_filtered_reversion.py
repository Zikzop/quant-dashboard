"""
Regime-filtered mean reversion — only active in non-trending, mean-revert regimes.
"""

from __future__ import annotations

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

import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegimeFilteredReversionConfig:
    zscore_entry: float = 1.5
    min_confidence: float = 0.25


class RegimeFilteredReversionAlpha(AlphaBase):
    """Z-score reversion gated by causal trend and vol regime filters."""

    def __init__(self, config: RegimeFilteredReversionConfig | None = None) -> None:
        self.config = config or RegimeFilteredReversionConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="regime_filtered_reversion",
                description=(
                    "Mean reversion active only when trend regime is RANGE and vol "
                    "is not expanding. Prevents naive reversion in trending markets."
                ),
                assumptions=(
                    "Regime labels computed causally from past data.",
                    "Reversion edge concentrated in range-bound periods.",
                ),
                failure_modes=(
                    "Regime misclassification activates reversion in trends.",
                    "Transition periods between regimes cause whipsaw.",
                ),
                regime_dependency=("RANGE", "LOW_VOL", "MEAN_REVERT"),
                holding_period="short",
                required_features=("close", "z_score", "rolling_volatility", "log_return"),
                expected_behavior="Near-zero score when filtered out; reversion signal otherwise.",
                family="mean_reversion",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config

        z = df["z_score"]
        reversion_raw = -z / cfg.zscore_entry
        trend = causal_trend_regime(df["close"])
        vol_reg = causal_vol_regime(df["log_return"])

        allowed = (trend == "RANGE") & (vol_reg != "HIGH_VOL")
        gate = allowed.astype(float)
        raw = reversion_raw * gate
        alpha_score = raw.apply(lambda x: self.sigmoid_score(x, scale=1.0))

        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg) * gate * 0.7 + 0.05
        )
        conf = conf.where(conf >= cfg.min_confidence, 0.0)

        warnings: list[str] = []
        if gate.mean() < 0.2:
            warnings.append("Reversion active <20% of sample — sparse signal.")

        vol = df["rolling_volatility"].replace(0, np.nan)
        exp_mean = raw * 0.002
        exp_std = vol.fillna(vol.median())
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("regime_gated", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(-0.2, index=df.index),
            distribution_interpretation=pd.Series(
                "Regime-filtered reversion; zero when trend/vol unfavorable.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"z_score": z, "regime_gate": gate},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=tuple(warnings))
