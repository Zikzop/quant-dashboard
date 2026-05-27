"""
Rolling risk budget — allocates total portfolio risk across strategies.

Instead of equal-weighting strategies, allocate risk budget proportional
to conviction and inversely proportional to realized volatility. This
ensures that low-vol strategies can take larger positions while high-vol
strategies are automatically constrained.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskBudgetAllocation:
    """Risk budget allocation across strategies."""

    strategy_budgets: dict[str, float]
    total_budget_used: float
    total_budget_available: float
    budget_utilization: float


class RollingRiskBudget:
    """
    Distributes portfolio-level risk budget across strategies.

    Each strategy gets a share of the total risk budget based on:
    - Its conviction weight (from alpha engine)
    - Its realized volatility (inverse vol weighting)
    - Remaining available budget after higher-priority allocations
    """

    def __init__(self, total_risk_budget: float = 0.15) -> None:
        self._total_budget = total_risk_budget

    def allocate(
        self,
        strategy_vols: dict[str, float],
        strategy_weights: dict[str, float] | None = None,
    ) -> RiskBudgetAllocation:
        if not strategy_vols:
            return RiskBudgetAllocation(
                strategy_budgets={},
                total_budget_used=0.0,
                total_budget_available=self._total_budget,
                budget_utilization=0.0,
            )

        inv_vols = {}
        for name, vol in strategy_vols.items():
            inv_vols[name] = 1.0 / max(vol, 0.01)

        total_inv = sum(inv_vols.values())
        risk_parity_weights = {k: v / total_inv for k, v in inv_vols.items()}

        if strategy_weights:
            combined = {}
            for name in risk_parity_weights:
                rp = risk_parity_weights[name]
                sw = strategy_weights.get(name, rp)
                combined[name] = 0.5 * rp + 0.5 * sw
            total_c = sum(combined.values())
            if total_c > 0:
                combined = {k: v / total_c for k, v in combined.items()}
        else:
            combined = risk_parity_weights

        budgets = {name: w * self._total_budget for name, w in combined.items()}
        total_used = sum(budgets.values())

        return RiskBudgetAllocation(
            strategy_budgets=budgets,
            total_budget_used=total_used,
            total_budget_available=self._total_budget,
            budget_utilization=total_used / self._total_budget if self._total_budget > 0 else 0.0,
        )
