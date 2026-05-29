"""
Covariance monitor — tracks the stability of the covariance matrix.

An unstable covariance matrix means the portfolio's risk profile is
changing rapidly. This can happen during:
- Regime transitions
- Structural breaks (e.g., Fed policy shifts)
- Market microstructure changes

The monitor compares recent and long-term covariance matrices to
detect instability using matrix distance metrics.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_engine.risk_config import CorrelationConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CovarianceStabilityReport:
    """Covariance stability assessment."""

    frobenius_distance: float
    max_eigenvalue_ratio: float
    trace_ratio: float
    is_unstable: bool
    instability_z_score: float
    condition_number: float
    n_assets: int


class CovarianceMonitor:
    """
    Detects covariance matrix instability by comparing short and long windows.

    Uses three complementary metrics:
    1. Frobenius distance: overall matrix difference
    2. Max eigenvalue ratio: structural shift in dominant risk factor
    3. Condition number: numerical stability / degeneracy risk
    """

    def __init__(self, config: CorrelationConfig | None = None) -> None:
        self._config = config or CorrelationConfig()
        self._distance_history: list[float] = []

    def assess(self, returns: pd.DataFrame) -> CovarianceStabilityReport:
        short_w = self._config.rolling_window_days
        long_w = self._config.long_window_days

        if len(returns) < long_w or returns.shape[1] < 2:
            return CovarianceStabilityReport(
                frobenius_distance=0.0,
                max_eigenvalue_ratio=1.0,
                trace_ratio=1.0,
                is_unstable=False,
                instability_z_score=0.0,
                condition_number=1.0,
                n_assets=returns.shape[1],
            )

        cov_short = returns.iloc[-short_w:].cov().values
        cov_long = returns.iloc[-long_w:].cov().values

        frob = float(np.linalg.norm(cov_short - cov_long, "fro"))
        norm_frob = frob / max(float(np.linalg.norm(cov_long, "fro")), 1e-9)
        self._distance_history.append(norm_frob)

        try:
            eig_short = np.sort(np.linalg.eigvalsh(cov_short))[::-1]
            eig_long = np.sort(np.linalg.eigvalsh(cov_long))[::-1]
            max_eig_ratio = float(eig_short[0] / max(eig_long[0], 1e-12))
        except np.linalg.LinAlgError:
            max_eig_ratio = 1.0

        trace_short = float(np.trace(cov_short))
        trace_long = float(np.trace(cov_long))
        trace_ratio = trace_short / max(trace_long, 1e-12)

        try:
            cond = float(np.linalg.cond(cov_short))
        except np.linalg.LinAlgError:
            cond = float("inf")

        if len(self._distance_history) >= 10:
            hist = np.array(self._distance_history)
            z_score = float((norm_frob - hist.mean()) / max(hist.std(), 1e-9))
        else:
            z_score = 0.0

        unstable = z_score > self._config.instability_z_threshold

        return CovarianceStabilityReport(
            frobenius_distance=norm_frob,
            max_eigenvalue_ratio=max_eig_ratio,
            trace_ratio=trace_ratio,
            is_unstable=unstable,
            instability_z_score=z_score,
            condition_number=cond,
            n_assets=returns.shape[1],
        )
