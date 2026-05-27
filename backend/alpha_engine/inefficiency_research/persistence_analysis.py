"""
Persistence analysis alpha — autocorrelation-based inefficiency research.

Documents behavioral underreaction / slow diffusion hypothesis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alpha_engine._regime_utils import causal_trend_regime, causal_vol_regime, regime_confidence
from alpha_engine.alpha_base import AlphaBase, AlphaSeriesOutput
from alpha_engine.alpha_metadata import AlphaMetadata


@dataclass(frozen=True)
class PersistenceAlphaConfig:
    acf_window: int = 40
    acf_lag: int = 5
    min_periods: int | None = None


class PersistenceAlpha(AlphaBase):
    """Multi-lag return persistence as probabilistic alpha."""

    def __init__(self, config: PersistenceAlphaConfig | None = None) -> None:
        self.config = config or PersistenceAlphaConfig()
        super().__init__(
            AlphaMetadata(
                alpha_name="persistence_analysis",
                description=(
                    "Research alpha from multi-lag return autocorrelation structure. "
                    "Behavioral: underreaction to information, herding lag."
                ),
                assumptions=(
                    "Autocorrelation stable over rolling window.",
                    "Persistence not fully arbitraged at measured horizon.",
                ),
                failure_modes=(
                    "Microstructure noise dominates at short lags.",
                    "Regime change erases persistence overnight.",
                    "Multiple testing across lags inflates false positives.",
                ),
                regime_dependency=("TRENDING", "POST_EARNINGS", "LOW_VOL"),
                holding_period="short",
                required_features=("log_return", "close", "rolling_volatility"),
                expected_behavior="Score scales with significant lag persistence.",
                family="inefficiency",
            )
        )

    def compute_series(self, df: pd.DataFrame) -> AlphaSeriesOutput:
        self._validate_input(df)
        cfg = self.config
        min_p = cfg.min_periods or cfg.acf_window
        rets = df["log_return"]

        def _lag_acf(x: np.ndarray) -> float:
            if len(x) < cfg.acf_lag + 5:
                return np.nan
            return float(pd.Series(x).autocorr(lag=cfg.acf_lag))

        persistence = rets.rolling(cfg.acf_window, min_periods=min_p).apply(_lag_acf, raw=True)
        vol = df["rolling_volatility"].replace(0, np.nan)
        raw = persistence / vol.replace(0, np.nan)
        alpha_score = raw.apply(lambda x: self.sigmoid_score(x, scale=0.1))

        trend = causal_trend_regime(df["close"])
        vol_reg = causal_vol_regime(rets)
        conf = self.clip_confidence(
            regime_confidence(trend, vol_reg, persistence=persistence.abs()) * 0.65 + 0.1
        )

        exp_std = vol.fillna(vol.median())
        exp_mean = persistence.fillna(0) * 0.002
        unc = 1.96 * exp_std

        warnings = (
            "Multiple testing risk: scan across lags inflates false discovery.",
        )

        out = self.build_output_frame(
            df.index,
            alpha_score=alpha_score,
            confidence=conf,
            trend_regime=trend,
            vol_regime=vol_reg,
            stationarity_hint=pd.Series("persistence", index=df.index),
            regime_confidence=conf,
            expected_mean=exp_mean,
            expected_std=exp_std,
            skew_hint=pd.Series(0.1, index=df.index),
            distribution_interpretation=pd.Series(
                "Lag persistence inefficiency; verify OOS before deployment.", index=df.index
            ),
            uncertainty_lower=exp_mean - unc,
            uncertainty_upper=exp_mean + unc,
            supporting={"persistence_acf": persistence, "lag": pd.Series(cfg.acf_lag, index=df.index)},
        )
        return AlphaSeriesOutput(outputs=out.dropna(), metadata=self.metadata, warnings=warnings)
