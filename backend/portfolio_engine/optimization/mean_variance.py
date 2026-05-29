"""
Mean-variance optimization — Markowitz with institutional constraints.

Solves the quadratic program:
    min  w'Σw - λ * μ'w
    s.t. constraint set C

Uses scipy.optimize with multiple constraint types.

Statistical assumptions:
- Returns are assumed to be drawn from a stationary multivariate distribution.
- The efficient frontier is only meaningful if expected returns are estimated
  with reasonable accuracy — estimation error in μ typically dominates.
- Markowitz is extremely sensitive to expected return inputs.

Known limitations:
- Mean-variance produces concentrated, unstable portfolios without constraints.
- The optimizer can produce corner solutions pinned to constraint bounds.
- Transaction costs and turnover penalties are approximated linearly.
- No robust optimization (e.g., worst-case or Bayesian shrinkage on μ).
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
class MVOConfig:
    risk_aversion: float = 2.5
    turnover_penalty: float = 0.005
    l2_regularization: float = 1e-4
    max_iterations: int = 1000
    convergence_tol: float = 1e-8


@dataclass(frozen=True)
class MVOResult:
    weights: PortfolioWeights
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    risk_contributions: dict[str, float]
    converged: bool
    objective_value: float
    warnings: list[str] = field(default_factory=list)


class MeanVarianceOptimizer:
    """
    Constrained mean-variance portfolio optimization.

    Supports long-only, leverage, turnover, and position-limit constraints.
    Includes L2 regularization to reduce sensitivity to expected return estimates.
    """

    def __init__(
        self,
        config: MVOConfig | None = None,
        constraints: PortfolioConstraints | None = None,
    ) -> None:
        self._config = config or MVOConfig()
        self._constraints = constraints or PortfolioConstraints()

    def optimize(
        self,
        expected_returns: pd.Series,
        covariance_matrix: pd.DataFrame,
        current_weights: dict[str, float] | None = None,
        timestamp: pd.Timestamp | None = None,
    ) -> MVOResult:
        cfg = self._config
        cons = self._constraints
        warnings: list[str] = []

        symbols = list(expected_returns.index)
        n = len(symbols)
        mu = expected_returns.values.astype(float)
        sigma = covariance_matrix.loc[symbols, symbols].values.astype(float)

        if current_weights is None:
            w_current = np.zeros(n)
        else:
            w_current = np.array([current_weights.get(s, 0.0) for s in symbols])

        if np.any(~np.isfinite(mu)):
            warnings.append("Non-finite expected returns, zeroing invalid entries")
            mu = np.where(np.isfinite(mu), mu, 0.0)

        if np.any(~np.isfinite(sigma)):
            warnings.append("Non-finite covariance entries, using diagonal")
            sigma = np.diag(np.maximum(np.diag(sigma), 1e-4))

        sigma += cfg.l2_regularization * np.eye(n)

        def objective(w: np.ndarray) -> float:
            port_var = w @ sigma @ w
            port_ret = mu @ w
            turnover_cost = cfg.turnover_penalty * np.sum(np.abs(w - w_current))
            reg = cfg.l2_regularization * np.sum(w ** 2)
            return float(port_var * cfg.risk_aversion - port_ret + turnover_cost + reg)

        def gradient(w: np.ndarray) -> np.ndarray:
            grad_var = 2 * cfg.risk_aversion * (sigma @ w)
            grad_ret = -mu
            grad_turn = cfg.turnover_penalty * np.sign(w - w_current)
            grad_reg = 2 * cfg.l2_regularization * w
            return grad_var + grad_ret + grad_turn + grad_reg

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

        w0 = np.ones(n) / n if cons.long_only else w_current.copy()
        if np.sum(np.abs(w0)) < 1e-8:
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
            warnings.append(f"MVO did not converge: {result.message}")

        port_var = float(w_opt @ sigma @ w_opt)
        port_vol = np.sqrt(max(port_var, 0.0))
        port_ret = float(mu @ w_opt)
        sharpe = port_ret / port_vol if port_vol > 1e-8 else 0.0

        rc = self._risk_contributions(w_opt, sigma, symbols)

        ts = timestamp or pd.Timestamp.now(tz="UTC")
        weights = PortfolioWeights(
            weights={symbols[i]: float(w_opt[i]) for i in range(n)},
            timestamp=ts,
            method="mean_variance",
            metadata={"risk_aversion": cfg.risk_aversion, "converged": converged},
        )

        return MVOResult(
            weights=weights,
            expected_return=port_ret,
            expected_risk=port_vol,
            sharpe_ratio=sharpe,
            risk_contributions=rc,
            converged=converged,
            objective_value=float(result.fun),
            warnings=warnings,
        )

    @staticmethod
    def _risk_contributions(
        w: np.ndarray, sigma: np.ndarray, symbols: list[str]
    ) -> dict[str, float]:
        sigma_w = sigma @ w
        port_var = w @ sigma_w
        if port_var <= 1e-12:
            return {s: 0.0 for s in symbols}
        port_vol = np.sqrt(port_var)
        mc = sigma_w / port_vol
        rc = w * mc
        rc_pct = rc / rc.sum() if abs(rc.sum()) > 1e-12 else rc
        return {symbols[i]: float(rc_pct[i]) for i in range(len(symbols))}
