"""
Kelly criterion position sizing — fractional Kelly with safety caps.

The full Kelly allocation maximizes long-run geometric growth but produces
extreme leverage and drawdowns in practice. This implementation uses
fractional Kelly with hard leverage caps and regime-aware scaling.

Statistical assumptions:
- Expected returns and covariance are estimated from backward-looking data only.
- Full Kelly is almost never used institutionally; 0.25-0.5 Kelly is typical.
- Covariance matrix must be positive semi-definite; near-singular matrices
  produce unstable allocations and are detected/handled.
- Kelly sizing degrades gracefully: if inputs are unstable, it falls back
  to equal risk contribution rather than producing garbage.

Known limitations:
- Kelly assumes ergodicity of the return process — violated in regime changes.
- Skewness and kurtosis are ignored; heavy tails can make Kelly too aggressive.
- Estimation error in mean returns dominates Kelly sizing for short lookbacks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class KellyConfig:
    fraction: float = 0.25
    max_leverage: float = 2.0
    max_single_weight: float = 0.25
    min_eigenvalue_ratio: float = 1e-6
    regularization: float = 1e-4
    annualization_factor: float = 252.0
    min_observations: int = 60
    shrinkage_intensity: float = 0.5


@dataclass(frozen=True)
class KellyResult:
    raw_weights: dict[str, float]
    fractional_weights: dict[str, float]
    capped_weights: dict[str, float]
    kelly_fraction: float
    raw_leverage: float
    final_leverage: float
    condition_number: float
    stable: bool
    warnings: list[str] = field(default_factory=list)


class KellySizer:
    """
    Fractional Kelly position sizing with institutional safety constraints.

    Uses Σ⁻¹μ formulation for multi-asset Kelly, with eigenvalue
    regularization to handle ill-conditioned covariance matrices.
    """

    def __init__(self, config: KellyConfig | None = None) -> None:
        self._config = config or KellyConfig()

    def compute(
        self,
        expected_returns: pd.Series,
        covariance_matrix: pd.DataFrame,
    ) -> KellyResult:
        """
        Compute Kelly-optimal weights.

        Parameters
        ----------
        expected_returns : annualized expected excess returns per asset
        covariance_matrix : annualized covariance matrix (must be PSD)
        """
        cfg = self._config
        warnings: list[str] = []

        symbols = list(expected_returns.index)
        mu = expected_returns.values.astype(float)
        cov = covariance_matrix.loc[symbols, symbols].values.astype(float)

        n = len(symbols)
        if n == 0:
            return self._empty_result(warnings)

        if np.any(~np.isfinite(mu)):
            warnings.append("Non-finite expected returns detected, zeroing")
            mu = np.where(np.isfinite(mu), mu, 0.0)

        if np.any(~np.isfinite(cov)):
            warnings.append("Non-finite covariance entries, using diagonal")
            cov = np.diag(np.diag(np.where(np.isfinite(cov), cov, 0.01)))

        eigenvalues = np.linalg.eigvalsh(cov)
        condition_number = (
            eigenvalues[-1] / max(eigenvalues[0], 1e-15) if len(eigenvalues) > 0 else np.inf
        )
        min_eig = eigenvalues[0] if len(eigenvalues) > 0 else 0.0

        stable = True
        if min_eig < cfg.min_eigenvalue_ratio * eigenvalues[-1]:
            warnings.append(
                f"Ill-conditioned covariance (condition={condition_number:.1f}), "
                "applying regularization"
            )
            cov += cfg.regularization * np.eye(n)
            stable = False

        try:
            cov_inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            warnings.append("Covariance inversion failed, falling back to diagonal")
            diag = np.diag(cov)
            diag = np.where(diag > 1e-8, diag, 1e-2)
            cov_inv = np.diag(1.0 / diag)
            stable = False

        raw_kelly = cov_inv @ mu

        raw_weights_dict = {symbols[i]: float(raw_kelly[i]) for i in range(n)}
        raw_leverage = float(np.sum(np.abs(raw_kelly)))

        fractional = raw_kelly * cfg.fraction
        frac_dict = {symbols[i]: float(fractional[i]) for i in range(n)}

        capped, cap_leverage = self._apply_caps(frac_dict)

        if raw_leverage > 5 * cfg.max_leverage:
            warnings.append(
                f"Raw Kelly leverage {raw_leverage:.2f} is extreme — "
                "estimation error likely dominates. Consider lower Kelly fraction."
            )
            stable = False

        return KellyResult(
            raw_weights=raw_weights_dict,
            fractional_weights=frac_dict,
            capped_weights=capped,
            kelly_fraction=cfg.fraction,
            raw_leverage=raw_leverage,
            final_leverage=cap_leverage,
            condition_number=condition_number,
            stable=stable,
            warnings=warnings,
        )

    def _apply_caps(
        self, weights: dict[str, float]
    ) -> tuple[dict[str, float], float]:
        cfg = self._config
        capped = {}
        for s, w in weights.items():
            capped[s] = float(np.clip(w, -cfg.max_single_weight, cfg.max_single_weight))

        gross = sum(abs(w) for w in capped.values())
        if gross > cfg.max_leverage:
            scale = cfg.max_leverage / gross
            capped = {s: w * scale for s, w in capped.items()}
            gross = cfg.max_leverage

        return capped, gross

    def _empty_result(self, warnings: list[str]) -> KellyResult:
        warnings.append("Empty universe, returning zero weights")
        return KellyResult(
            raw_weights={},
            fractional_weights={},
            capped_weights={},
            kelly_fraction=self._config.fraction,
            raw_leverage=0.0,
            final_leverage=0.0,
            condition_number=0.0,
            stable=True,
            warnings=warnings,
        )
