"""
Minimum variance portfolio optimization.

The minimum variance portfolio minimizes portfolio risk without requiring
expected return estimates. This makes it more robust than MVO when
return forecasts are unreliable.

    min  w'Σw
    s.t. Σw_i = 1  (or leverage constraint)
         w_i ∈ [lb, ub]

Statistical assumptions:
- Covariance is a reasonable forward-looking risk proxy.
- The minimum variance portfolio is NOT necessarily efficient — it sacrifices
  expected return for risk minimization.
- More stable than MVO because it doesn't depend on expected returns.

Known limitations:
- Tends to concentrate in low-volatility assets, potentially ignoring alpha.
- Sensitive to covariance estimation error, especially in small-n/large-p settings.
- The optimal portfolio can change substantially with small covariance perturbations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from portfolio_engine.portfolio_base import PortfolioConstraints, PortfolioWeights

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MinVarConfig:
    l2_regularization: float = 1e-4
    max_iterations: int = 1000
    convergence_tol: float = 1e-8


@dataclass(frozen=True)
class MinVarResult:
    weights: PortfolioWeights
    portfolio_volatility: float
    risk_contributions: dict[str, float]
    converged: bool
    warnings: list[str] = field(default_factory=list)


class MinimumVarianceOptimizer:
    """
    Minimum variance portfolio with configurable constraints.
    """

    def __init__(
        self,
        config: MinVarConfig | None = None,
        constraints: PortfolioConstraints | None = None,
    ) -> None:
        self._config = config or MinVarConfig()
        self._constraints = constraints or PortfolioConstraints()

    def optimize(
        self,
        covariance_matrix: pd.DataFrame,
        timestamp: pd.Timestamp | None = None,
    ) -> MinVarResult:
        cfg = self._config
        cons = self._constraints
        warnings: list[str] = []

        symbols = list(covariance_matrix.columns)
        n = len(symbols)
        sigma = covariance_matrix.values.astype(float)
        sigma += cfg.l2_regularization * np.eye(n)

        def objective(w: np.ndarray) -> float:
            return float(w @ sigma @ w)

        def gradient(w: np.ndarray) -> np.ndarray:
            return 2 * sigma @ w

        if cons.long_only:
            bounds = [(max(0.0, cons.min_weight), cons.max_weight) for _ in range(n)]
        else:
            bounds = [(-cons.max_weight, cons.max_weight) for _ in range(n)]

        scipy_constraints = []
        if cons.long_only:
            scipy_constraints.append({
                "type": "eq",
                "fun": lambda w: np.sum(w) - 1.0,
            })
        else:
            scipy_constraints.append({
                "type": "ineq",
                "fun": lambda w: cons.max_gross_leverage - np.sum(np.abs(w)),
            })

        w0 = np.ones(n) / n

        result = minimize(
            objective,
            w0,
            jac=gradient,
            method="SLSQP",
            bounds=bounds,
            constraints=scipy_constraints,
            options={"maxiter": cfg.max_iterations, "ftol": cfg.convergence_tol},
        )

        w_opt = result.x
        converged = result.success
        if not converged:
            warnings.append(f"MinVar did not converge: {result.message}")

        port_var = float(w_opt @ sigma @ w_opt)
        port_vol = np.sqrt(max(port_var, 0.0))

        sigma_w = sigma @ w_opt
        if port_var > 1e-12:
            mc = sigma_w / np.sqrt(port_var)
            rc = w_opt * mc
            rc_sum = rc.sum()
            rc_pct = rc / rc_sum if abs(rc_sum) > 1e-12 else rc
        else:
            rc_pct = np.ones(n) / n

        ts = timestamp or pd.Timestamp.now(tz="UTC")
        weights = PortfolioWeights(
            weights={symbols[i]: float(w_opt[i]) for i in range(n)},
            timestamp=ts,
            method="minimum_variance",
        )

        return MinVarResult(
            weights=weights,
            portfolio_volatility=port_vol,
            risk_contributions={symbols[i]: float(rc_pct[i]) for i in range(n)},
            converged=converged,
            warnings=warnings,
        )
