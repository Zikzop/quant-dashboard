"""
Feature importance analysis: MI, permutation importance, rolling importance.

IMPORTANT: Feature importance measures predictive association in-sample or
on held-out data. It does NOT establish causality, economic mechanism, or
post-cost tradability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import permutation_importance

from feature_analysis.mutual_information import (
    CAUSALITY_DISCLAIMER,
    MutualInformationReport,
    compute_mutual_information,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PermutationImportanceResult:
    feature: str
    importance_mean: float
    importance_std: float
    rank: int


@dataclass(frozen=True)
class RollingImportanceResult:
    feature: str
    rolling_mean_importance: float
    importance_std: float
    trend_slope: float


@dataclass(frozen=True)
class FeatureImportanceConfig:
    rolling_window: int = 60
    min_periods: int | None = None
    n_permutations: int = 10
    random_state: int = 42
    rf_n_estimators: int = 100


@dataclass(frozen=True)
class FeatureImportanceReport:
    mutual_information: MutualInformationReport
    permutation: tuple[PermutationImportanceResult, ...]
    rolling: tuple[RollingImportanceResult, ...] | None
    disclaimer: str
    summary: str
    warnings: tuple[str, ...]


def analyze_feature_importance(
    features: pd.DataFrame,
    target: pd.Series,
    *,
    config: FeatureImportanceConfig | None = None,
    compute_rolling: bool = True,
) -> FeatureImportanceReport:
    """
    Comprehensive feature importance analysis.

    Uses a simple RandomForest as a nonlinear baseline model for permutation
    importance. Forest is fit on provided data only — caller must ensure
    train/test separation to avoid leakage.
    """
    cfg = config or FeatureImportanceConfig()
    warnings: list[str] = [CAUSALITY_DISCLAIMER]

    aligned = features.copy()
    y = pd.Series(target).reindex(aligned.index)
    mask = y.notna() & aligned.notna().all(axis=1)
    X = aligned.loc[mask].astype(float)
    y_clean = y.loc[mask].astype(float)

    if len(X) < 50:
        warnings.append("Sample size < 50: importance rankings may not generalize.")

    mi_report = compute_mutual_information(X, y_clean, random_state=cfg.random_state)
    perm = _permutation_importance(X, y_clean, cfg)
    rolling = (
        _rolling_importance(X, y_clean, cfg)
        if compute_rolling and len(X) >= cfg.rolling_window + 10
        else None
    )

    top_perm = perm[0].feature if perm else "n/a"
    summary = (
        f"Top permutation feature: {top_perm}. "
        f"MI top: {mi_report.scores[0].feature if mi_report.scores else 'n/a'}. "
        "Importance ≠ causality."
    )

    return FeatureImportanceReport(
        mutual_information=mi_report,
        permutation=perm,
        rolling=rolling,
        disclaimer=CAUSALITY_DISCLAIMER,
        summary=summary,
        warnings=tuple(warnings),
    )


def _permutation_importance(
    X: pd.DataFrame,
    y: pd.Series,
    cfg: FeatureImportanceConfig,
) -> tuple[PermutationImportanceResult, ...]:
    model = RandomForestRegressor(
        n_estimators=cfg.rf_n_estimators,
        random_state=cfg.random_state,
        n_jobs=-1,
    )
    model.fit(X.values, y.values)

    result = permutation_importance(
        model,
        X.values,
        y.values,
        n_repeats=cfg.n_permutations,
        random_state=cfg.random_state,
        n_jobs=-1,
    )

    ranked = sorted(
        zip(X.columns, result.importances_mean, result.importances_std),
        key=lambda x: x[1],
        reverse=True,
    )

    return tuple(
        PermutationImportanceResult(
            feature=str(name),
            importance_mean=float(mean),
            importance_std=float(std),
            rank=i + 1,
        )
        for i, (name, mean, std) in enumerate(ranked)
    )


def _rolling_importance(
    X: pd.DataFrame,
    y: pd.Series,
    cfg: FeatureImportanceConfig,
) -> tuple[RollingImportanceResult, ...]:
    min_p = cfg.min_periods or cfg.rolling_window
    results: list[RollingImportanceResult] = []

    for col in X.columns:
        importances: list[float] = []
        for end in range(cfg.rolling_window, len(X) + 1):
            start = end - cfg.rolling_window
            window_X = X.iloc[start:end]
            window_y = y.iloc[start:end]
            if window_X.isna().any().any() or window_y.isna().any():
                continue
            model = RandomForestRegressor(
                n_estimators=min(50, cfg.rf_n_estimators),
                random_state=cfg.random_state,
                n_jobs=-1,
            )
            model.fit(window_X[[col]].values, window_y.values)
            importances.append(float(model.feature_importances_[0]))

        if not importances:
            continue

        arr = np.array(importances)
        x_axis = np.arange(len(arr))
        slope = float(np.polyfit(x_axis, arr, 1)[0]) if len(arr) > 1 else 0.0

        results.append(
            RollingImportanceResult(
                feature=col,
                rolling_mean_importance=float(arr.mean()),
                importance_std=float(arr.std(ddof=1)) if len(arr) > 1 else 0.0,
                trend_slope=slope,
            )
        )

    return tuple(sorted(results, key=lambda r: r.rolling_mean_importance, reverse=True))
