"""
Volatility mean reversion — fade vol spikes expecting compression.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata


@dataclass(frozen=True)
class VolatilityReversionConfig:
    vol_zscore_window: int = 60
    min_periods: int | None = None


class VolatilityReversionAlpha(AlphaBase):
    """Probabilistic bet on vol compression after extreme realized vol."""

    def __init__(self, config: VolatilityReversionConfig | None = None) -> None:
        self.config = config or VolatilityReversionConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="volatility_reversion",
                description=(
                    "Exploits volatility clustering mean-reversion: extreme realized vol "
                    "tends to compress. Structural: inventory/risk limits force de-grossing."
                ),
                assumptions=(
                    "Vol mean-reverts over medium horizon.",
                    "Vol z-score uses expanding/rolling past data only.",
                ),
                failure_modes=(
                    "Regime transitions sustain elevated vol (crisis persistence).",
                    "Vol of vol too high for point estimates.",
                ),
                regime_dependency=("HIGH_VOL", "POST_CRISIS"),
                holding_period="medium",
                required_features=("rolling_volatility", "realized_volatility", "log_return", "close"),
                expected_behavior="Score reflects expected vol compression direction.",
                family="mean_reversion",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config
        min_p = cfg.min_periods or cfg.vol_zscore_window

        vol = df["rolling_volatility"]
        vol_mean = vol.rolling(cfg.vol_zscore_window, min_periods=min_p).mean()
        vol_std = vol.rolling(cfg.vol_zscore_window, min_periods=min_p).std().replace(0, np.nan)
        vol_z = (vol - vol_mean) / vol_std

        reversion = -vol_z
        alpha_score = reversion.apply(lambda x: self.sigmoid_score(x, scale=1.5))

        trend = causal_trend_regime(df["close"])
        vol_reg = causal_vol_regime(df["log_return"])
        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg) * (vol_z.abs() / 2).clip(0, 1) * 0.5 + 0.15
        )

        exp_std = vol.fillna(vol.median())
        exp_mean = reversion * 0.001
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("vol_mean_revert", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.0, index=df.index),
            distribution_interpretation=pd.Series(
                "Vol compression expectation; not directional price alpha alone.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"vol_z": vol_z, "vol_level": vol},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=())
