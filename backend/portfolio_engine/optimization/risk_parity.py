"""
Risk parity portfolio optimization.

Equalizes risk contributions across assets:
    RC_i = w_i * (Σw)_i / σ_p = 1/N  for all i

Uses the Spinu (2013) / Maillard, Roncalli, Teïlétche (2010) formulation
with iterative Newton-Raphson and fallback bisection.

Statistical assumptions:
- Risk is measured by variance contribution — tail risk is not captured.
- Equal risk contribution is NOT optimal if assets have different alphas.
- Covariance must be positive definite for unique solution.

Known limitations:
- Standard risk parity ignores expected returns entirely.
- Concentrated factor exposures can hide behind equal risk contributions.
- Transaction costs from rebalancing can erode the diversification benefit.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from portfolio_engine.portfolio_base import PortfolioConstraints, PortfolioWeights

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskParityConfig:
    max_iterations: int = 500
    convergence_tol: float = 1e-8
    regularization: float = 1e-6
    max_leverage: float = 1.5


@dataclass(frozen=True)
class RiskParityResult:
    weights: PortfolioWeights
    risk_contributions: dict[str, float]
    portfolio_volatility: float
    budget_tracking_error: float
    converged: bool
    iterations: int
    warnings: list[str] = field(default_factory=list)


class RiskParityOptimizer:
    """
    Equal risk contribution portfolio.

    Iteratively adjusts weights until each asset contributes equally to
    total portfolio variance. Uses multiplicative update rule for stability.
    """

    def __init__(
        self,
        config: RiskParityConfig | None = None,
        constraints: PortfolioConstraints | None = None,
    ) -> None:
        self._config = config or RiskParityConfig()
        self._constraints = constraints or PortfolioConstraints(long_only=True)

    def optimize(
        self,
        covariance_matrix: pd.DataFrame,
        risk_budgets: dict[str, float] | None = None,
        timestamp: pd.Timestamp | None = None,
    ) -> RiskParityResult:
        cfg = self._config
        warnings: list[str] = []

        symbols = list(covariance_matrix.columns)
        n = len(symbols)
        sigma = covariance_matrix.values.astype(float)
        sigma += cfg.regularization * np.eye(n)

        if risk_budgets is None:
            budgets = np.ones(n) / n
        else:
            budgets = np.array([risk_budgets.get(s, 1.0 / n) for s in symbols])
            bsum = budgets.sum()
            if abs(bsum - 1.0) > 1e-6:
                budgets /= bsum

        w = np.ones(n) / n
        converged = False
        iteration = 0

        for iteration in range(cfg.max_iterations):
            sigma_w = sigma @ w
            port_var = float(w @ sigma_w)
            if port_var <= 0:
                w = np.ones(n) / n
                warnings.append("Non-positive portfolio variance during iteration")
                break

            port_vol = np.sqrt(port_var)
            mc = sigma_w / port_vol
            rc = w * mc
            rc_sum = rc.sum()

            if abs(rc_sum) < 1e-12:
                break

            rc_frac = rc / rc_sum
            w_new = w * np.sqrt(budgets / np.maximum(rc_frac, 1e-12))
            w_new /= w_new.sum()

            if np.max(np.abs(w_new - w)) < cfg.convergence_tol:
                converged = True
                w = w_new
                break
            w = w_new

        if self._constraints.long_only:
            w = np.maximum(w, 0.0)
            w_sum = w.sum()
            if w_sum > 1e-12:
                w /= w_sum

        max_w = self._constraints.max_weight
        w = np.minimum(w, max_w)
        w_sum = w.sum()
        if w_sum > 1e-12:
            w /= w_sum

        gross = float(np.sum(np.abs(w)))
        if gross > cfg.max_leverage:
            w *= cfg.max_leverage / gross

        sigma_w = sigma @ w
        port_var = float(w @ sigma_w)
        port_vol = float(np.sqrt(max(port_var, 0.0)))

        if port_vol > 1e-12:
            mc = sigma_w / port_vol
            rc = w * mc
            rc_sum = rc.sum()
            rc_frac = rc / rc_sum if abs(rc_sum) > 1e-12 else budgets
        else:
            rc_frac = budgets

        tracking = float(np.sqrt(np.sum((rc_frac - budgets) ** 2)))

        if not converged:
            warnings.append(f"Risk parity did not converge in {iteration + 1} iterations")

        ts = timestamp or pd.Timestamp.now(tz="UTC")
        weights = PortfolioWeights(
            weights={symbols[i]: float(w[i]) for i in range(n)},
            timestamp=ts,
            method="risk_parity",
        )

        return RiskParityResult(
            weights=weights,
            risk_contributions={symbols[i]: float(rc_frac[i]) for i in range(n)},
            portfolio_volatility=port_vol,
            budget_tracking_error=tracking,
            converged=converged,
            iterations=iteration + 1,
            warnings=warnings,
        )
