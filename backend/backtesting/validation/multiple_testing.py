"""
Multiple testing corrections — controls false discovery rate.

When testing many strategies, some will appear significant by chance.
Bonferroni controls the family-wise error rate (conservative).
Benjamini-Hochberg controls the false discovery rate (less conservative).
Holm-Bonferroni is a step-down procedure (middle ground).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MultipleTestingResult:
    """Results of multiple testing correction."""

    method: str
    n_tests: int
    original_p_values: tuple[float, ...]
    adjusted_p_values: tuple[float, ...]
    significant_at_005: tuple[bool, ...]
    n_significant: int
    n_rejected: int
    effective_threshold: float
    warnings: tuple[str, ...]


def bonferroni_correction(
    p_values: list[float] | np.ndarray,
) -> MultipleTestingResult:
    """
    Bonferroni correction — most conservative.

    Adjusted p-value = min(p * n_tests, 1.0)
    """
    p = np.array(p_values)
    n = len(p)
    adjusted = np.minimum(p * n, 1.0)
    sig = adjusted < 0.05
    threshold = 0.05 / n

    warnings = []
    if n > 50:
        warnings.append(
            f"Bonferroni with {n} tests is extremely conservative — "
            f"consider Benjamini-Hochberg instead"
        )

    return MultipleTestingResult(
        method="bonferroni",
        n_tests=n,
        original_p_values=tuple(p.tolist()),
        adjusted_p_values=tuple(adjusted.tolist()),
        significant_at_005=tuple(sig.tolist()),
        n_significant=int(sig.sum()),
        n_rejected=int((~sig).sum()),
        effective_threshold=threshold,
        warnings=tuple(warnings),
    )


def benjamini_hochberg(
    p_values: list[float] | np.ndarray,
    fdr: float = 0.05,
) -> MultipleTestingResult:
    """
    Benjamini-Hochberg procedure — controls false discovery rate.

    Less conservative than Bonferroni. Appropriate when testing
    many strategies and willing to accept some false positives.
    """
    p = np.array(p_values)
    n = len(p)
    sorted_idx = np.argsort(p)
    sorted_p = p[sorted_idx]

    adjusted = np.empty(n)
    adjusted[sorted_idx[-1]] = sorted_p[-1]
    for i in range(n - 2, -1, -1):
        rank = i + 1
        bh_value = sorted_p[i] * n / rank
        adjusted[sorted_idx[i]] = min(bh_value, adjusted[sorted_idx[i + 1]])

    adjusted = np.minimum(adjusted, 1.0)
    sig = adjusted < fdr

    threshold_candidates = sorted_p[sorted_p <= fdr * np.arange(1, n + 1) / n]
    effective_threshold = float(threshold_candidates[-1]) if len(threshold_candidates) > 0 else 0.0

    warnings = []
    fdr_rate = int(sig.sum()) / max(n, 1)
    if fdr_rate > 0.5:
        warnings.append(
            f"High discovery rate ({fdr_rate:.0%}) — verify signals are independent"
        )

    return MultipleTestingResult(
        method="benjamini_hochberg",
        n_tests=n,
        original_p_values=tuple(p.tolist()),
        adjusted_p_values=tuple(adjusted.tolist()),
        significant_at_005=tuple(sig.tolist()),
        n_significant=int(sig.sum()),
        n_rejected=int((~sig).sum()),
        effective_threshold=effective_threshold,
        warnings=tuple(warnings),
    )


def holm_bonferroni(
    p_values: list[float] | np.ndarray,
    alpha: float = 0.05,
) -> MultipleTestingResult:
    """Holm-Bonferroni step-down procedure — uniformly more powerful than Bonferroni."""
    p = np.array(p_values)
    n = len(p)
    sorted_idx = np.argsort(p)
    sorted_p = p[sorted_idx]

    adjusted = np.empty(n)
    for i in range(n):
        adjusted[sorted_idx[i]] = min(sorted_p[i] * (n - i), 1.0)

    for i in range(1, n):
        adjusted[sorted_idx[i]] = max(adjusted[sorted_idx[i]], adjusted[sorted_idx[i - 1]])

    sig = adjusted < alpha

    return MultipleTestingResult(
        method="holm_bonferroni",
        n_tests=n,
        original_p_values=tuple(p.tolist()),
        adjusted_p_values=tuple(adjusted.tolist()),
        significant_at_005=tuple(sig.tolist()),
        n_significant=int(sig.sum()),
        n_rejected=int((~sig).sum()),
        effective_threshold=alpha / n,
        warnings=(),
    )
