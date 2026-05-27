"""
Covariance matrix estimation — multiple estimators with shrinkage.

Provides rolling, exponentially weighted, and Ledoit-Wolf shrinkage estimators.
All estimators produce symmetric, positive semi-definite matrices.

Statistical assumptions:
- Sample covariance is unbiased but noisy for p/n > 0.1 (Marchenko-Pastur).
- Ledoit-Wolf shrinkage toward scaled identity reduces estimation error
  when the number of assets is large relative to history.
- EWM covariance emphasizes recent structure, appropriate for non-stationary markets.

Known limitations:
- All estimators assume continuous returns — not valid for illiquid assets.
- Covariance is a second-moment measure only; tail dependencies and
  copula structures are not captured.
- Shrinkage intensity is data-adaptive but the target (identity) may be
  suboptimal for factor-structured universes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@unique
class CovarianceMethod(Enum):
    SAMPLE = "sample"
    EWM = "ewm"
    LEDOIT_WOLF = "ledoit_wolf"
    ROLLING = "rolling"


@dataclass(frozen=True)
class CovarianceConfig:
    method: CovarianceMethod = CovarianceMethod.LEDOIT_WOLF
    lookback_days: int = 252
    ewm_halflife: int = 60
    min_observations: int = 60
    annualization_factor: float = 252.0
    shrinkage_target: str = "constant_correlation"
    regularization_floor: float = 1e-6
    max_condition_number: float = 1e6


@dataclass(frozen=True)
class CovarianceResult:
    covariance: pd.DataFrame
    correlation: pd.DataFrame
    method: CovarianceMethod
    n_observations: int
    condition_number: float
    shrinkage_intensity: float
    eigenvalue_ratio: float
    is_well_conditioned: bool
    warnings: list[str] = field(default_factory=list)


class CovarianceEstimator:
    """
    Multi-method covariance estimation with conditioning diagnostics.

    All methods enforce positive semi-definiteness via eigenvalue flooring
    and produce symmetric matrices.
    """

    def __init__(self, config: CovarianceConfig | None = None) -> None:
        self._config = config or CovarianceConfig()

    def estimate(self, returns: pd.DataFrame) -> CovarianceResult:
        cfg = self._config
        warnings: list[str] = []

        clean = returns.dropna()
        if len(clean) < cfg.min_observations:
            warnings.append(
                f"Insufficient observations ({len(clean)} < {cfg.min_observations})"
            )

        clean = clean.iloc[-cfg.lookback_days:]
        n_obs = len(clean)
        n_assets = clean.shape[1]

        if n_obs < n_assets:
            warnings.append(
                f"Underdetermined: {n_obs} obs < {n_assets} assets. "
                "Shrinkage strongly recommended."
            )

        if cfg.method == CovarianceMethod.SAMPLE:
            cov = self._sample_covariance(clean, cfg.annualization_factor)
            shrinkage = 0.0
        elif cfg.method == CovarianceMethod.EWM:
            cov = self._ewm_covariance(clean, cfg.ewm_halflife, cfg.annualization_factor)
            shrinkage = 0.0
        elif cfg.method == CovarianceMethod.LEDOIT_WOLF:
            cov, shrinkage = self._ledoit_wolf(clean, cfg.annualization_factor)
        elif cfg.method == CovarianceMethod.ROLLING:
            cov = self._sample_covariance(clean, cfg.annualization_factor)
            shrinkage = 0.0
        else:
            raise ValueError(f"Unknown method: {cfg.method}")

        cov = self._ensure_psd(cov, cfg.regularization_floor)
        cov = (cov + cov.T) / 2

        eigenvalues = np.linalg.eigvalsh(cov.values)
        cond = eigenvalues[-1] / max(eigenvalues[0], 1e-15)
        eig_ratio = eigenvalues[0] / max(eigenvalues[-1], 1e-15)
        well_conditioned = cond < cfg.max_condition_number

        if not well_conditioned:
            warnings.append(
                f"Ill-conditioned matrix (condition={cond:.1f}). "
                "Portfolio optimization may be unstable."
            )

        cov_arr = cov.values.copy()
        vols = np.sqrt(np.diag(cov_arr))
        vol_outer = np.outer(vols, vols)
        vol_outer = np.where(vol_outer > 1e-12, vol_outer, 1.0)
        corr_arr = cov_arr / vol_outer
        np.fill_diagonal(corr_arr, 1.0)
        corr = pd.DataFrame(corr_arr, index=cov.index, columns=cov.columns)

        return CovarianceResult(
            covariance=cov,
            correlation=corr,
            method=cfg.method,
            n_observations=n_obs,
            condition_number=cond,
            shrinkage_intensity=shrinkage,
            eigenvalue_ratio=eig_ratio,
            is_well_conditioned=well_conditioned,
            warnings=warnings,
        )

    @staticmethod
    def _sample_covariance(
        returns: pd.DataFrame, annualization: float
    ) -> pd.DataFrame:
        return returns.cov() * annualization

    @staticmethod
    def _ewm_covariance(
        returns: pd.DataFrame, halflife: int, annualization: float
    ) -> pd.DataFrame:
        ewm = returns.ewm(halflife=halflife, min_periods=max(halflife, 20))
        cov = ewm.cov().iloc[-len(returns.columns):]
        cov.index = cov.index.droplevel(0) if isinstance(cov.index, pd.MultiIndex) else cov.index
        return cov * annualization

    @staticmethod
    def _ledoit_wolf(
        returns: pd.DataFrame, annualization: float
    ) -> tuple[pd.DataFrame, float]:
        """
        Ledoit-Wolf shrinkage toward constant-correlation target.

        Analytical optimal shrinkage intensity per Ledoit & Wolf (2004).
        """
        X = returns.values
        T, N = X.shape

        mean = X.mean(axis=0)
        X_centered = X - mean
        sample_cov = (X_centered.T @ X_centered) / T

        var = np.diag(sample_cov)
        std = np.sqrt(var)
        std_outer = np.outer(std, std)
        std_outer = np.where(std_outer > 1e-12, std_outer, 1.0)

        corr = sample_cov / std_outer
        np.fill_diagonal(corr, 1.0)
        avg_corr = (corr.sum() - N) / (N * (N - 1))

        target = avg_corr * std_outer
        np.fill_diagonal(target, var)

        delta = sample_cov - target
        X2 = X_centered ** 2

        pi_hat = 0.0
        for i in range(N):
            for j in range(i, N):
                pij = np.mean(
                    (X_centered[:, i] * X_centered[:, j] - sample_cov[i, j]) ** 2
                )
                pi_hat += pij if i == j else 2 * pij

        gamma = np.sum(delta ** 2)

        shrinkage = max(0.0, min(1.0, (pi_hat / T) / gamma)) if gamma > 1e-12 else 1.0

        shrunk = shrinkage * target + (1 - shrinkage) * sample_cov

        cov_df = pd.DataFrame(
            shrunk * annualization,
            index=returns.columns,
            columns=returns.columns,
        )
        return cov_df, shrinkage

    @staticmethod
    def _ensure_psd(
        cov: pd.DataFrame, floor: float
    ) -> pd.DataFrame:
        vals, vecs = np.linalg.eigh(cov.values)
        vals = np.maximum(vals, floor)
        fixed = vecs @ np.diag(vals) @ vecs.T
        return pd.DataFrame(fixed, index=cov.index, columns=cov.columns)
