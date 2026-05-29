"""
Volatility-adjusted momentum — risk-normalized trend conviction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata


@dataclass(frozen=True)
class VolAdjMomentumConfig:
    momentum_window: int = 60
    vol_window: int = 20
    min_periods: int | None = None


class VolatilityAdjustedMomentumAlpha(AlphaBase):
    """Sharpe-like momentum: cumulative return divided by realized volatility."""

    def __init__(self, config: VolAdjMomentumConfig | None = None) -> None:
        self.config = config or VolAdjMomentumConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="volatility_adjusted_momentum",
                description=(
                    "Ranks trend conviction by return per unit of realized volatility. "
                    "Institutional preference for risk-adjusted trend exposure."
                ),
                assumptions=(
                    "Realized vol is a reasonable forward risk proxy (imperfect).",
                    "Momentum horizon matches vol estimation window scale.",
                ),
                failure_modes=(
                    "Vol collapse inflates adjusted momentum artificially.",
                    "Crisis regimes: vol spikes faster than momentum decays.",
                ),
                regime_dependency=("UPTREND", "DOWNTREND", "NORMAL_VOL"),
                holding_period="medium",
                required_features=("close", "log_return", "rolling_volatility"),
                expected_behavior="High score when trend strong relative to vol.",
                family="momentum",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config
        min_p = cfg.min_periods or cfg.momentum_window

        cum_ret = df["log_return"].rolling(cfg.momentum_window, min_periods=min_p).sum()
        vol = df["rolling_volatility"].replace(0, np.nan)
        vol_adj = (cum_ret / vol).replace([np.inf, -np.inf], np.nan)
        alpha_score = vol_adj.apply(lambda x: self.sigmoid_score(x, scale=2.0))

        trend = causal_trend_regime(df["close"])
        vol_reg = causal_vol_regime(df["log_return"])
        conf = self.clip_confidence(regime_confidence(trend, vol_reg) * 0.75 + 0.1)

        exp_std = vol.fillna(vol.median())
        exp_mean = vol_adj.fillna(0) * 0.001
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("vol_adj_mom", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.0, index=df.index),
            distribution_interpretation=pd.Series(
                "Vol-normalized momentum; lower tail risk than raw momentum.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"vol_adj_momentum": vol_adj, "cum_return": cum_ret},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=())
