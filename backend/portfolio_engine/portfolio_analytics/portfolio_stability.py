"""
Portfolio stability analysis — rolling assessment of weight and risk stability.

Measures how stable the portfolio construction outputs are over time.
Instability indicates estimation noise dominating the optimization,
which erodes performance through excessive turnover.

Metrics:
- Weight stability: rolling autocorrelation of weight vectors
- Optimization stability: sensitivity of weights to covariance perturbation
- Turnover persistence: rolling average realized turnover
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StabilityReport:
    weight_autocorrelation: float
    avg_weight_change: float
    max_weight_change: float
    rolling_turnover_mean: float
    rolling_turnover_std: float
    perturbation_sensitivity: float
    stability_score: float
    regime: str
    warnings: list[str] = field(default_factory=list)


class PortfolioStabilityAnalyzer:
    """
    Assess portfolio weight stability from weight history.

    Computes rolling stability metrics and flags regimes where
    optimization instability is likely eroding performance.
    """

    def __init__(
        self,
        lookback: int = 20,
        instability_threshold: float = 0.3,
    ) -> None:
        self._lookback = lookback
        self._instability_threshold = instability_threshold

    def analyze(
        self,
        weight_history: pd.DataFrame,
        covariance_matrix: pd.DataFrame | None = None,
    ) -> StabilityReport:
        """
        Parameters
        ----------
        weight_history : DataFrame with DatetimeIndex, columns = asset symbols,
                         values = weights at each rebalance point.
        covariance_matrix : current covariance for perturbation analysis.
        """
        warnings: list[str] = []
        n_periods = len(weight_history)

        if n_periods < 3:
            return StabilityReport(
                weight_autocorrelation=1.0, avg_weight_change=0.0,
                max_weight_change=0.0, rolling_turnover_mean=0.0,
                rolling_turnover_std=0.0, perturbation_sensitivity=0.0,
                stability_score=1.0, regime="insufficient_data",
                warnings=["Insufficient weight history for stability analysis"],
            )

        diffs = weight_history.diff().dropna()
        abs_changes = diffs.abs()

        avg_change = float(abs_changes.values.mean())
        max_change = float(abs_changes.values.max())

        turnover = abs_changes.sum(axis=1) / 2.0
        window = min(self._lookback, len(turnover))
        rolling_to = turnover.rolling(window, min_periods=2)
        to_mean = float(rolling_to.mean().iloc[-1]) if len(turnover) > 1 else 0.0
        to_std = float(rolling_to.std().iloc[-1]) if len(turnover) > 2 else 0.0

        autocorrs = []
        for col in weight_history.columns:
            series = weight_history[col].dropna()
            if len(series) > 2:
                ac = float(series.autocorr(lag=1))
                if np.isfinite(ac):
                    autocorrs.append(ac)
        weight_ac = float(np.mean(autocorrs)) if autocorrs else 1.0

        pert_sensitivity = 0.0
        if covariance_matrix is not None and len(weight_history.columns) >= 2:
            pert_sensitivity = self._perturbation_sensitivity(
                weight_history.iloc[-1].values,
                covariance_matrix.loc[
                    weight_history.columns, weight_history.columns
                ].values,
            )

        stability = float(np.clip(
            weight_ac * (1.0 - to_mean / max(0.1, 1.0)) * (1.0 - pert_sensitivity),
            0.0, 1.0,
        ))

        if stability < 0.3:
            regime = "unstable"
            warnings.append(
                f"Portfolio stability score {stability:.3f} is low. "
                "Optimization may be dominated by estimation noise."
            )
        elif stability < 0.6:
            regime = "moderate"
        else:
            regime = "stable"

        return StabilityReport(
            weight_autocorrelation=weight_ac,
            avg_weight_change=avg_change,
            max_weight_change=max_change,
            rolling_turnover_mean=to_mean,
            rolling_turnover_std=to_std,
            perturbation_sensitivity=pert_sensitivity,
            stability_score=stability,
            regime=regime,
            warnings=warnings,
        )

    @staticmethod
    def _perturbation_sensitivity(
        weights: np.ndarray,
        cov: np.ndarray,
        n_perturbations: int = 50,
        perturbation_scale: float = 0.05,
    ) -> float:
        """
        Measure weight sensitivity to small covariance perturbations.

        Perturbs the covariance matrix and measures how much the
        minimum-variance weights change. High sensitivity = instability.
        """
        n = len(weights)
        if n < 2:
            return 0.0

        rng = np.random.default_rng(42)
        weight_diffs = []

        for _ in range(n_perturbations):
            noise = rng.normal(0, perturbation_scale, (n, n))
            noise = (noise + noise.T) / 2
            perturbed = cov + noise * np.sqrt(np.diag(cov)[:, None] * np.diag(cov)[None, :])
            eigenvalues = np.linalg.eigvalsh(perturbed)
            if eigenvalues[0] < 1e-8:
                perturbed += (1e-6 - eigenvalues[0]) * np.eye(n)

            try:
                inv = np.linalg.inv(perturbed)
                ones = np.ones(n)
                w_mv = inv @ ones / (ones @ inv @ ones)
                diff = np.sqrt(np.mean((w_mv - weights) ** 2))
                weight_diffs.append(diff)
            except np.linalg.LinAlgError:
                continue

        return float(np.mean(weight_diffs)) if weight_diffs else 0.0
