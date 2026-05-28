"""
Regime transition-matrix engine (P1.4).

Models regime persistence probabilistically from a discrete regime label
sequence (the HMM history). Treats the regime path as a first-order Markov
chain and estimates the row-stochastic transition matrix

    P[i, j] = P(regime_{t+1} = j | regime_t = i)

Exports, in the API payload:
* the full transition matrix and raw counts,
* per-state persistence  p_ii  and expected dwell time  1 / (1 - p_ii),
* the stationary distribution (long-run regime mix),
* an instability score in [0, 1] (frequency-weighted switching propensity),
* an instability flag.

Statistical caveats (deliberately surfaced, not hidden):
* A first-order Markov assumption ignores duration dependence; real regime
  durations are typically non-geometric. Expected dwell time is therefore a
  first-order approximation.
* Estimates from short windows are high-variance; we apply optional Laplace
  smoothing and report the sample size so consumers can discount accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence

import numpy as np

# Canonical regime ordering for stable matrix layout across requests.
CANONICAL_REGIMES = ("MEAN_REVERT", "TRENDING", "CRISIS")

# A window producing fewer than this many transitions is flagged low-confidence.
_MIN_TRANSITIONS_CONFIDENT = 20


@dataclass(frozen=True)
class RegimeTransitionModel:
    states: list[str]
    counts: Dict[str, Dict[str, int]]
    matrix: Dict[str, Dict[str, float]]
    persistence: Dict[str, float]
    expected_duration: Dict[str, float]
    stationary_distribution: Dict[str, float]
    instability_score: float
    is_unstable: bool
    n_transitions: int
    low_confidence: bool
    current_state: str | None

    def to_payload(self) -> dict:
        return {
            "states": self.states,
            "matrix": self.matrix,
            "counts": self.counts,
            "persistence": self.persistence,
            "expected_duration": self.expected_duration,
            "stationary_distribution": self.stationary_distribution,
            "instability_score": round(self.instability_score, 4),
            "is_unstable": self.is_unstable,
            "n_transitions": self.n_transitions,
            "low_confidence": self.low_confidence,
            "current_state": self.current_state,
        }


def _resolve_states(labels: Sequence[str]) -> list[str]:
    observed = [s for s in CANONICAL_REGIMES if s in set(labels)]
    extra = sorted({s for s in labels if s not in CANONICAL_REGIMES})
    return observed + extra if (observed or extra) else list(CANONICAL_REGIMES)


def _stationary_distribution(matrix: np.ndarray, states: list[str]) -> Dict[str, float]:
    """Left eigenvector of P for eigenvalue 1 (long-run regime mix)."""
    n = matrix.shape[0]
    if n == 0:
        return {}
    try:
        values, vectors = np.linalg.eig(matrix.T)
        idx = int(np.argmin(np.abs(values - 1.0)))
        vec = np.real(vectors[:, idx])
        total = vec.sum()
        if total == 0 or not np.isfinite(total):
            raise ValueError("degenerate stationary vector")
        dist = np.abs(vec) / np.abs(vec).sum()
    except Exception:
        dist = np.full(n, 1.0 / n)
    return {states[i]: round(float(dist[i]), 4) for i in range(n)}


def build_transition_model(
    labels: Sequence[str],
    *,
    instability_threshold: float = 0.5,
    laplace_smoothing: float = 0.0,
    current_state: str | None = None,
) -> RegimeTransitionModel:
    """Estimate a first-order Markov transition model from a label sequence."""
    clean = [str(x) for x in labels if x is not None and str(x) not in {"", "nan", "UNKNOWN"}]
    states = _resolve_states(clean)
    index = {s: i for i, s in enumerate(states)}
    n = len(states)

    counts = np.zeros((n, n), dtype=float)
    n_transitions = 0
    for a, b in zip(clean[:-1], clean[1:]):
        if a in index and b in index:
            counts[index[a], index[b]] += 1
            n_transitions += 1

    smoothed = counts + laplace_smoothing
    row_sums = smoothed.sum(axis=1, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        matrix = np.divide(
            smoothed, row_sums, out=np.zeros_like(smoothed), where=row_sums > 0
        )
    # Rows for never-observed source states stay all-zero; mark self-absorbing
    # so the chain is well-formed for stationary analysis.
    for i in range(n):
        if row_sums[i, 0] == 0:
            matrix[i, i] = 1.0

    persistence = {states[i]: float(matrix[i, i]) for i in range(n)}
    expected_duration = {
        states[i]: (float(1.0 / (1.0 - matrix[i, i])) if matrix[i, i] < 1.0 else float("inf"))
        for i in range(n)
    }

    # Frequency-weighted switching propensity. Weight each source state by how
    # often it was visited so rare states don't dominate the score.
    visit_counts = counts.sum(axis=1)
    visit_total = visit_counts.sum()
    if visit_total > 0:
        weights = visit_counts / visit_total
        instability = float(np.sum(weights * (1.0 - np.diag(matrix))))
    else:
        instability = 0.0

    matrix_dict = {
        states[i]: {states[j]: round(float(matrix[i, j]), 4) for j in range(n)}
        for i in range(n)
    }
    counts_dict = {
        states[i]: {states[j]: int(counts[i, j]) for j in range(n)} for i in range(n)
    }

    return RegimeTransitionModel(
        states=states,
        counts=counts_dict,
        matrix=matrix_dict,
        persistence={k: round(v, 4) for k, v in persistence.items()},
        expected_duration={
            k: (round(v, 2) if np.isfinite(v) else None) for k, v in expected_duration.items()
        },
        stationary_distribution=_stationary_distribution(matrix, states),
        instability_score=instability,
        is_unstable=instability >= instability_threshold,
        n_transitions=n_transitions,
        low_confidence=n_transitions < _MIN_TRANSITIONS_CONFIDENT,
        current_state=current_state if current_state in index else (clean[-1] if clean else None),
    )
