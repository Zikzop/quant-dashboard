"""
Mutual information between features and target.

Measures nonlinear statistical dependence. High MI indicates association,
NOT causation or tradable alpha.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.feature_selection import mutual_info_regression

logger = logging.getLogger(__name__)

CAUSALITY_DISCLAIMER = (
    "Mutual information measures statistical dependence, not causality. "
    "High MI may reflect spurious correlation, lookahead, or regime confounding."
)


@dataclass(frozen=True)
class MutualInformationResult:
    feature: str
    mi_score: float
    rank: int


@dataclass(frozen=True)
class MutualInformationReport:
    scores: tuple[MutualInformationResult, ...]
    disclaimer: str
    warnings: tuple[str, ...]


def compute_mutual_information(
    features: pd.DataFrame,
    target: pd.Series,
    *,
    n_neighbors: int = 5,
    random_state: int = 42,
) -> MutualInformationReport:
    """
    Compute mutual information scores for each feature vs target.

    Parameters
    ----------
    features : pd.DataFrame
        Feature matrix (no future columns).
    target : pd.Series
        Target aligned on same index. Must be known only at decision time
        to avoid leakage (e.g. forward return shifted appropriately).
    """
    warnings: list[str] = [CAUSALITY_DISCLAIMER]

    aligned = features.copy()
    y = pd.Series(target).reindex(aligned.index)
    mask = y.notna() & aligned.notna().all(axis=1)
    X = aligned.loc[mask].astype(float)
    y_clean = y.loc[mask].astype(float)

    if len(X) < 30:
        warnings.append("Sample size < 30: MI estimates may be unstable.")
        logger.warning("MI: small sample size n=%d", len(X))

    mi_scores = mutual_info_regression(
        X.values,
        y_clean.values,
        n_neighbors=n_neighbors,
        random_state=random_state,
    )

    ranked = sorted(
        zip(X.columns, mi_scores),
        key=lambda x: x[1],
        reverse=True,
    )

    results = tuple(
        MutualInformationResult(feature=str(name), mi_score=float(score), rank=i + 1)
        for i, (name, score) in enumerate(ranked)
    )

    return MutualInformationReport(
        scores=results,
        disclaimer=CAUSALITY_DISCLAIMER,
        warnings=tuple(warnings),
    )
