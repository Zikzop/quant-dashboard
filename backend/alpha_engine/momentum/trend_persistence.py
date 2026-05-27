"""
Trend persistence alpha — probabilistic momentum from return autocorrelation structure.

Uses backward-looking rolling persistence, not crossover signals.
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

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrendPersistenceConfig:
    persistence_window: int = 40
    momentum_window: int = 20
    min_periods: int | None = None


class TrendPersistenceAlpha(AlphaBase):
    """Rolling return persistence and trend strength, volatility-normalized."""

    def __init__(self, config: TrendPersistenceConfig | None = None) -> None:
        self.config = config or TrendPersistenceConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="trend_persistence",
                description=(
                    "Exploits short-horizon return persistence when trends exhibit "
                    "autocorrelated structure. Structural rationale: slow information "
                    "diffusion and positioning inertia."
                ),
                assumptions=(
                    "Persistence measurable over rolling window without structural break.",
                    "Transaction costs do not dominate small persistent moves.",
                ),
                failure_modes=(
                    "Mean-reverting chop destroys persistence signal.",
                    "Regime shifts invalidate historical autocorrelation.",
                    "Crowded momentum unwinds (factor crash).",
                ),
                regime_dependency=("UPTREND", "DOWNTREND", "STRONG_TREND"),
                holding_period="medium",
                required_features=("close", "log_return", "pct_return", "rolling_volatility"),
                expected_behavior="Positive alpha_score when persistence and trend align.",
                family="momentum",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config
        min_p = cfg.min_periods or cfg.persistence_window

        close = df["close"]
        rets = df["log_return"]
        vol = df["rolling_volatility"].replace(0, np.nan)

        def _persist(x: np.ndarray) -> float:
            if len(x) < 5:
                return np.nan
            s = pd.Series(x)
            return float(s.autocorr(lag=1))

        persistence = rets.rolling(cfg.persistence_window, min_periods=min_p).apply(
            _persist, raw=True
        )
        mom = close.pct_change(cfg.momentum_window)
        trend_strength = (mom / vol).replace([np.inf, -np.inf], np.nan)

        raw_score = persistence * np.sign(trend_strength)
        alpha_score = raw_score.apply(lambda x: self.sigmoid_score(x, scale=0.5))

        trend = causal_trend_regime(close)
        vol_reg = causal_vol_regime(rets)
        trending = is_trending_regime(trend)
        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg, persistence=persistence.abs())
            * trending.astype(float)
            * 0.7
            + 0.15
        )

        exp_std = vol.fillna(vol.median())
        exp_mean = trend_strength.fillna(0) * 0.01
        unc = 1.96 * exp_std

        warnings: list[str] = []
        if (persistence.dropna() < 0).mean() > 0.5:
            warnings.append("Majority negative persistence — momentum assumption weak.")

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("trend_persistence", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.0, index=df.index),
            distribution_interpretation=pd.Series(
                "Persistence-weighted momentum; fat tails likely.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={
                "persistence": persistence,
                "trend_strength": trend_strength,
            },
        )

        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=tuple(warnings))
