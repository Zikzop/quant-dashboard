"""
Risk budgeting position sizing.

Allocates capital based on risk budgets — each asset or strategy receives a
target fraction of total portfolio risk. This is the foundation for risk
parity and strategy-level risk allocation.

Statistical assumptions:
- Risk contributions are computed via marginal risk decomposition:
  RC_i = w_i * (Σw)_i / σ_p
- Covariance is assumed to be a reasonable estimate of forward risk structure.
- Non-linear effects (fat tails, jumps) are not captured by variance-based budgets.

Known limitations:
- Covariance instability makes risk budgets drift between rebalances.
- Concentrated risk budgets can produce high-turnover allocations.
- Equal risk budgets may not be optimal if assets have heterogeneous alpha.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskBudgetConfig:
    max_weight: float = 0.25
    min_weight: float = 0.0
    max_leverage: float = 1.5
    convergence_tol: float = 1e-8
    max_iterations: int = 500
    regularization: float = 1e-6


@dataclass(frozen=True)
class RiskBudgetResult:
    weights: dict[str, float]
    risk_contributions: dict[str, float]
    risk_budget_target: dict[str, float]
    tracking_error: float
    portfolio_vol: float
    converged: bool
    iterations: int
    warnings: list[str] = field(default_factory=list)


class RiskBudgetSizer:
    """
    Allocate weights to match target risk budget using iterative optimization.

    Uses the Spinu (2013) formulation: find w such that
    RC_i / σ_p = b_i for all i, where b is the risk budget vector.
    """

    def __init__(self, config: RiskBudgetConfig | None = None) -> None:
        self._config = config or RiskBudgetConfig()

    def compute(
        self,
        covariance_matrix: pd.DataFrame,
        risk_budgets: dict[str, float] | None = None,
    ) -> RiskBudgetResult:
        """
        Compute risk-budget-matched weights.

        Parameters
        ----------
        covariance_matrix : annualized asset covariance
        risk_budgets : target risk fraction per asset (sums to 1).
                       If None, equal risk budgets are used.
        """
        cfg = self._config
        warnings: list[str] = []
        symbols = list(covariance_matrix.columns)
        n = len(symbols)

        if n == 0:
            return RiskBudgetResult(
                weights={}, risk_contributions={}, risk_budget_target={},
                tracking_error=0.0, portfolio_vol=0.0, converged=True,
                iterations=0, warnings=["Empty universe"],
            )

        cov = covariance_matrix.values.astype(float)
        cov += cfg.regularization * np.eye(n)

        if risk_budgets is None:
            budgets = np.ones(n) / n
            budget_dict = {s: 1.0 / n for s in symbols}
        else:
            budgets = np.array([risk_budgets.get(s, 1.0 / n) for s in symbols])
            budget_sum = budgets.sum()
            if abs(budget_sum - 1.0) > 1e-6:
                budgets /= budget_sum
                warnings.append(f"Risk budgets renormalized from sum={budget_sum:.4f}")
            budget_dict = {symbols[i]: float(budgets[i]) for i in range(n)}

        w = budgets.copy()
        converged = False

        for iteration in range(cfg.max_iterations):
            sigma_w = cov @ w
            port_var = float(w @ sigma_w)
            if port_var <= 0:
                w = budgets.copy()
                warnings.append("Non-positive portfolio variance, resetting to budgets")
                break

            port_vol = np.sqrt(port_var)
            marginal = sigma_w / port_vol
            rc = w * marginal

            rc_frac = rc / rc.sum() if rc.sum() > 1e-12 else budgets

            w_new = w * (budgets / np.maximum(rc_frac, 1e-12))
            w_new = w_new / w_new.sum()

            if np.max(np.abs(w_new - w)) < cfg.convergence_tol:
                converged = True
                w = w_new
                break

            w = w_new

        w = np.clip(w, cfg.min_weight, cfg.max_weight)
        w_sum = w.sum()
        if w_sum > 1e-12:
            w /= w_sum

        gross = float(np.sum(np.abs(w)))
        if gross > cfg.max_leverage:
            w *= cfg.max_leverage / gross

        sigma_w = cov @ w
        port_var = float(w @ sigma_w)
        port_vol = float(np.sqrt(max(port_var, 0.0)))

        if port_vol > 1e-12:
            rc_final = w * (sigma_w / port_vol)
            rc_frac = rc_final / rc_final.sum() if rc_final.sum() > 1e-12 else budgets
        else:
            rc_frac = budgets

        tracking = float(np.sqrt(np.sum((rc_frac - budgets) ** 2)))

        weights_dict = {symbols[i]: float(w[i]) for i in range(n)}
        rc_dict = {symbols[i]: float(rc_frac[i]) for i in range(n)}

        if not converged:
            warnings.append(
                f"Risk budget optimization did not converge in {cfg.max_iterations} iterations"
            )

        return RiskBudgetResult(
            weights=weights_dict,
            risk_contributions=rc_dict,
            risk_budget_target=budget_dict,
            tracking_error=tracking,
            portfolio_vol=port_vol,
            converged=converged,
            iterations=iteration + 1 if not converged else iteration + 1,
            warnings=warnings,
        )
