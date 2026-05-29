"""
Relative strength alpha — cross-sectional rank mapped to probabilistic score.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata
from alpha_engine.cross_sectional.ranking_engine import CrossSectionalRankingEngine, RankingConfig


@dataclass(frozen=True)
class RelativeStrengthConfig:
    lookback: int = 60
    rank_method: str = "percentile"


class RelativeStrengthAlpha(AlphaBase):
    """
    Single-asset wrapper: compares asset momentum to synthetic peer percentile.

    For true multi-asset, use CrossSectionalRankingEngine directly on universe.
    """

    def __init__(self, config: RelativeStrengthConfig | None = None) -> None:
        self.config = config or RelativeStrengthConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="relative_strength",
                description=(
                    "Cross-sectional momentum rank within a supplied universe. "
                    "Institutional long-short equity/stat-arb building block."
                ),
                assumptions=(
                    "Universe homogenous enough for comparable ranking.",
                    "Lookback aligned with rebalancing frequency.",
                ),
                failure_modes=(
                    "Heterogeneous assets (FX vs equities) distort ranks.",
                    "Survivorship bias in universe construction.",
                    "Factor crowding on popular momentum ranks.",
                ),
                regime_dependency=("RISK_ON", "TRENDING", "BROAD_MARKET"),
                holding_period="medium",
                required_features=("close", "log_return", "rolling_volatility"),
                expected_behavior="High score for top-quintile relative momentum.",
                family="cross_sectional",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        close = df["close"]
        mom = close.pct_change(self.config.lookback)
        vol = df["rolling_volatility"].replace(0, np.nan)
        vol_adj = (mom / vol).replace([np.inf, -np.inf], np.nan)

        expanding_rank = vol_adj.expanding(min_periods=self.config.lookback).rank(pct=True)
        alpha_score = (expanding_rank * 2 - 1).apply(lambda x: self.sigmoid_score(x, scale=1.0))

        from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence

        trend = causal_trend_regime(close)
        vol_reg = causal_vol_regime(df["log_return"])
        conf = self.clip_confidence(regime_confidence(trend, vol_reg) * 0.65 + 0.15)

        exp_std = vol.fillna(vol.median())
        exp_mean = (expanding_rank - 0.5) * 0.004
        unc = 1.96 * exp_std

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("cross_sectional", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.2, index=df.index),
            distribution_interpretation=pd.Series(
                "Relative strength percentile; universe-dependent.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"relative_rank": expanding_rank, "vol_adj_mom": vol_adj},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=())

    @staticmethod
    def rank_universe(prices: pd.DataFrame, config: RankingConfig | None = None):
        """Multi-asset cross-sectional ranking entry point."""
        return CrossSectionalRankingEngine(config).rank(prices)
