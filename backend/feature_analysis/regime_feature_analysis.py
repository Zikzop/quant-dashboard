"""
Regime-conditioned feature analysis.

Examines how feature distributions and target relationships vary across
volatility, trend, and transition regimes. Correlation by regime is
descriptive, not causal.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RegimeType = Literal["volatility", "trend", "custom"]


@dataclass(frozen=True)
class RegimeStats:
    regime: str
    n_obs: int
    feature_mean: float
    feature_std: float
    target_mean: float
    correlation: float
    interpretation: str


@dataclass(frozen=True)
class FeatureRegimeProfile:
    feature: str
    regimes: tuple[RegimeStats, ...]
    max_correlation_spread: float
    transition_sensitive: bool


@dataclass(frozen=True)
class RegimeFeatureReport:
    regime_column: str
    features: tuple[FeatureRegimeProfile, ...]
    volatility_dependent: tuple[str, ...]
    trend_dependent: tuple[str, ...]
    summary: str
    warnings: tuple[str, ...]


def analyze_regime_features(
    features: pd.DataFrame,
    target: pd.Series,
    regime: pd.Series,
    *,
    min_regime_obs: int = 20,
    spread_threshold: float = 0.3,
) -> RegimeFeatureReport:
    """
    Analyze feature behavior conditional on regime labels.

    Parameters
    ----------
    features : pd.DataFrame
        Feature columns.
    target : pd.Series
        Target (no lookahead).
    regime : pd.Series
        Regime labels aligned with features index.
    """
    warnings: list[str] = [
        "Regime-conditioned correlations describe association, not causality.",
        "Regime labels must be computed causally (no full-sample peeking).",
    ]

    regime_aligned = regime.reindex(features.index)
    profiles: list[FeatureRegimeProfile] = []
    vol_dependent: list[str] = []
    trend_dependent: list[str] = []

    for col in features.columns:
        feat = features[col].astype(float)
        tgt = pd.Series(target).reindex(features.index).astype(float)
        profile = _profile_feature(col, feat, tgt, regime_aligned, min_regime_obs)
        profiles.append(profile)

        if profile.max_correlation_spread > spread_threshold:
            regime_name = str(regime_aligned.name or regime.name or "").lower()
            if "vol" in regime_name or any(
                "vol" in r.regime.lower() or "high" in r.regime.lower()
                for r in profile.regimes
            ):
                vol_dependent.append(col)
            if "trend" in regime_name or any(
                "trend" in r.regime.lower() for r in profile.regimes
            ):
                trend_dependent.append(col)

    transition_count = sum(1 for p in profiles if p.transition_sensitive)
    summary = (
        f"Analyzed {len(profiles)} features across {regime_aligned.nunique()} regimes. "
        f"{transition_count} transition-sensitive."
    )

    return RegimeFeatureReport(
        regime_column=str(regime.name or "regime"),
        features=tuple(profiles),
        volatility_dependent=tuple(vol_dependent),
        trend_dependent=tuple(trend_dependent),
        summary=summary,
        warnings=tuple(warnings),
    )


def classify_volatility_regime(
    returns: pd.Series,
    *,
    window: int = 20,
    quantile: float = 0.75,
) -> pd.Series:
    """Backward-looking volatility regime: HIGH_VOL vs LOW_VOL."""
    vol = returns.rolling(window, min_periods=window).std()
    threshold = vol.expanding(min_periods=window).quantile(quantile)
    regime = pd.Series("LOW_VOL", index=returns.index)
    regime[vol >= threshold] = "HIGH_VOL"
    regime[vol.isna()] = np.nan
    regime.name = "vol_regime"
    return regime


def classify_trend_regime(
    prices: pd.Series,
    *,
    window: int = 50,
) -> pd.Series:
    """Backward-looking trend regime from rolling return sign."""
    rolling_ret = prices.pct_change(window)
    regime = pd.Series("RANGE", index=prices.index)
    regime[rolling_ret > 0] = "UPTREND"
    regime[rolling_ret < 0] = "DOWNTREND"
    regime[rolling_ret.isna()] = np.nan
    regime.name = "trend_regime"
    return regime


def _profile_feature(
    name: str,
    feature: pd.Series,
    target: pd.Series,
    regime: pd.Series,
    min_obs: int,
) -> FeatureRegimeProfile:
    regime_stats: list[RegimeStats] = []
    corrs: list[float] = []

    for label in sorted(regime.dropna().unique(), key=str):
        mask = regime == label
        if mask.sum() < min_obs:
            continue
        f = feature.loc[mask]
        t = target.loc[mask]
        corr = float(f.corr(t)) if len(f) > 2 else float("nan")
        if not np.isnan(corr):
            corrs.append(corr)

        regime_stats.append(
            RegimeStats(
                regime=str(label),
                n_obs=int(mask.sum()),
                feature_mean=float(f.mean()),
                feature_std=float(f.std(ddof=1)) if len(f) > 1 else 0.0,
                target_mean=float(t.mean()),
                correlation=corr if not np.isnan(corr) else 0.0,
                interpretation=f"{name} in {label}: corr={corr:.3f}, n={mask.sum()}.",
            )
        )

    spread = max(corrs) - min(corrs) if len(corrs) >= 2 else 0.0
    transition_sensitive = spread > 0.3

    return FeatureRegimeProfile(
        feature=name,
        regimes=tuple(regime_stats),
        max_correlation_spread=float(spread),
        transition_sensitive=transition_sensitive,
    )
