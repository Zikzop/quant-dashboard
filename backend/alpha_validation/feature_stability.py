"""
Feature stability analysis: drift, persistence, and regime sensitivity.

Detects features that change predictive relationship over time — a common
source of backtest alpha that fails live.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

StabilityLabel = Literal["stable", "moderate_drift", "unstable", "insufficient_data"]


@dataclass(frozen=True)
class FeatureStabilityConfig:
    rolling_window: int = 60
    min_periods: int | None = None
    drift_threshold: float = 0.3
    persistence_lag: int = 1


@dataclass(frozen=True)
class FeatureDriftResult:
    feature: str
    mean_correlation: float
    correlation_std: float
    drift_score: float
    persistence: float
    stability: StabilityLabel
    interpretation: str


@dataclass(frozen=True)
class FeatureStabilityReport:
    target: str
    features: tuple[FeatureDriftResult, ...]
    regime_sensitive: tuple[str, ...]
    overall_stability: StabilityLabel
    summary: str
    warnings: tuple[str, ...]


def analyze_feature_stability(
    features: pd.DataFrame,
    target: pd.Series,
    *,
    config: FeatureStabilityConfig | None = None,
    regime: pd.Series | None = None,
) -> FeatureStabilityReport:
    """
    Analyze rolling feature-target correlation, persistence, and drift.

    Parameters
    ----------
    features : pd.DataFrame
        Feature columns aligned with target index.
    target : pd.Series
        Forward-looking target must NOT be used — pass contemporaneous
        or lagged target only to avoid leakage.
    regime : optional pd.Series
        Regime labels for sensitivity analysis (same index as features).
    """
    cfg = config or FeatureStabilityConfig()
    min_p = cfg.min_periods or cfg.rolling_window
    warnings: list[str] = []

    aligned = features.copy()
    tgt = pd.Series(target).reindex(aligned.index)
    valid_mask = tgt.notna()
    aligned = aligned.loc[valid_mask]
    tgt = tgt.loc[valid_mask]

    if len(aligned) < cfg.rolling_window + 5:
        return FeatureStabilityReport(
            target=str(target.name or "target"),
            features=(),
            regime_sensitive=(),
            overall_stability="insufficient_data",
            summary="Insufficient data for feature stability analysis.",
            warnings=("Increase sample size.",),
        )

    results: list[FeatureDriftResult] = []
    regime_sensitive: list[str] = []

    for col in aligned.columns:
        feat = aligned[col].astype(float)
        rolling_corr = feat.rolling(cfg.rolling_window, min_periods=min_p).corr(tgt)
        valid_corr = rolling_corr.dropna()

        if valid_corr.empty:
            continue

        mean_corr = float(valid_corr.mean())
        corr_std = float(valid_corr.std(ddof=1)) if len(valid_corr) > 1 else 0.0
        drift_score = corr_std / (abs(mean_corr) + 1e-9)
        persistence = float(feat.autocorr(lag=cfg.persistence_lag))

        stability = _classify_stability(drift_score, cfg.drift_threshold)
        interp = (
            f"{col}: mean_corr={mean_corr:.3f}, drift={drift_score:.2f}, "
            f"persistence={persistence:.3f} -> {stability}."
        )

        if stability == "unstable":
            logger.warning("Feature %s unstable (drift=%.2f)", col, drift_score)

        results.append(
            FeatureDriftResult(
                feature=col,
                mean_correlation=mean_corr,
                correlation_std=corr_std,
                drift_score=drift_score,
                persistence=persistence,
                stability=stability,
                interpretation=interp,
            )
        )

        if regime is not None:
            if _regime_sensitive(feat, tgt, regime.reindex(aligned.index)):
                regime_sensitive.append(col)

    if not results:
        return FeatureStabilityReport(
            target=str(target.name or "target"),
            features=(),
            regime_sensitive=(),
            overall_stability="insufficient_data",
            summary="No valid feature correlations computed.",
            warnings=(),
        )

    unstable_frac = sum(1 for r in results if r.stability == "unstable") / len(results)
    if unstable_frac > 0.5:
        overall: StabilityLabel = "unstable"
        summary = f"{unstable_frac:.0%} features unstable; alpha likely regime-dependent."
    elif unstable_frac > 0.2:
        overall = "moderate_drift"
        summary = "Moderate feature drift detected; validate OOS."
    else:
        overall = "stable"
        summary = "Feature relationships relatively stable over sample."

    warnings.append(
        "Correlation stability ≠ causal stability. "
        "Feature-target correlation does not imply tradable edge."
    )

    return FeatureStabilityReport(
        target=str(target.name or "target"),
        features=tuple(results),
        regime_sensitive=tuple(regime_sensitive),
        overall_stability=overall,
        summary=summary,
        warnings=tuple(warnings),
    )


def _classify_stability(drift_score: float, threshold: float) -> StabilityLabel:
    if drift_score > threshold * 2:
        return "unstable"
    if drift_score > threshold:
        return "moderate_drift"
    return "stable"


def _regime_sensitive(
    feature: pd.Series,
    target: pd.Series,
    regime: pd.Series,
    *,
    min_obs: int = 20,
) -> bool:
    """True if feature-target correlation differs materially across regimes."""
    corrs: list[float] = []
    for label in regime.dropna().unique():
        mask = regime == label
        if mask.sum() < min_obs:
            continue
        c = feature.loc[mask].corr(target.loc[mask])
        if not np.isnan(c):
            corrs.append(float(c))

    if len(corrs) < 2:
        return False
    return max(corrs) - min(corrs) > 0.3
