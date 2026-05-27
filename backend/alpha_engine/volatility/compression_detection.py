"""
Volatility compression detection — ATR and realized vol contraction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata


@dataclass(frozen=True)
class CompressionConfig:
    compression_window: int = 20
    baseline_window: int = 60
    min_periods: int | None = None


class CompressionDetectionAlpha(AlphaBase):
    """Probabilistic compression score from ATR and realized vol contraction."""

    def __init__(self, config: CompressionConfig | None = None) -> None:
        self.config = config or CompressionConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="compression_detection",
                description=(
                    "Identifies volatility compression phases that often precede "
                    "range expansion. Rationale: market maker inventory equilibrium."
                ),
                assumptions=(
                    "Compression measurable via ATR/realized vol ratio to baseline.",
                    "Compression duration finite (spring coiling metaphor).",
                ),
                failure_modes=(
                    "Extended low-vol grind without breakout (theta decay).",
                    "Macro event bypasses compression signal.",
                ),
                regime_dependency=("LOW_VOL", "COMPRESSED", "RANGE"),
                holding_period="short",
                required_features=("atr", "rolling_volatility", "close", "log_return"),
                expected_behavior="High compression score before expansion events.",
                family="volatility",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config
        min_p = cfg.min_periods or cfg.baseline_window

        atr = df["atr"]
        vol = df["rolling_volatility"]
        atr_base = atr.rolling(cfg.baseline_window, min_periods=min_p).mean()
        vol_base = vol.rolling(cfg.baseline_window, min_periods=min_p).mean()

        atr_ratio = (atr / atr_base.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        vol_ratio = (vol / vol_base.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)
        compression = 1.0 - ((atr_ratio + vol_ratio) / 2.0).clip(0, 2) / 2.0
        alpha_score = compression.apply(lambda x: self.sigmoid_score(x * 2 - 1, scale=0.5))

        trend = causal_trend_regime(df["close"])
        vol_reg = causal_vol_regime(df["log_return"])
        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg) * compression.clip(0, 1) * 0.5 + 0.2
        )

        exp_std = vol.fillna(vol.median())
        exp_mean = compression * 0.001
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("compression", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.0, index=df.index),
            distribution_interpretation=pd.Series(
                "Compression phase; breakout direction undetermined.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"compression": compression, "atr_ratio": atr_ratio},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=())
