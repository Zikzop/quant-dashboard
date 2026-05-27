"""
Confidence aggregation utilities for multi-alpha portfolios.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AggregatedConfidence:
    mean_confidence: float
    min_confidence: float
    effective_n: float
    interpretation: str


def aggregate_confidence(confidences: dict[str, float]) -> AggregatedConfidence:
    """
    Aggregate per-alpha confidence with effective sample size penalty.

    Low minimum confidence drags aggregate — weakest link principle.
    """
    if not confidences:
        raise ValueError("confidences dict is empty")

    values = np.array(list(confidences.values()), dtype=float)
    mean_c = float(values.mean())
    min_c = float(values.min())
    effective_n = float(len(values) * min_c)

    if min_c < 0.2:
        interp = "Low minimum confidence — composite unreliable."
    elif mean_c > 0.6 and min_c > 0.3:
        interp = "Strong aggregate confidence across alphas."
    else:
        interp = "Moderate aggregate confidence; monitor weak components."

    return AggregatedConfidence(
        mean_confidence=mean_c,
        min_confidence=min_c,
        effective_n=effective_n,
        interpretation=interp,
    )
