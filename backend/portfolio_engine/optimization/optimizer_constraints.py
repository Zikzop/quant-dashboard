"""
Unified constraint specification and validation for portfolio optimizers.

Translates PortfolioConstraints into scipy-compatible constraint objects
and provides pre/post-optimization constraint checking.

This module serves as the constraint adapter layer between the portfolio
engine's domain-specific constraints and the numerical optimizer's
mathematical constraint representations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from portfolio_engine.portfolio_base import PortfolioConstraints

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConstraintViolation:
    constraint_name: str
    limit: float
    actual: float
    severity: str  # "warning" | "hard"

    @property
    def message(self) -> str:
        return (
            f"[{self.severity}] {self.constraint_name}: "
            f"actual={self.actual:.6f}, limit={self.limit:.6f}"
        )


@dataclass(frozen=True)
class ConstraintCheckResult:
    satisfied: bool
    violations: list[ConstraintViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build_scipy_constraints(
    constraints: PortfolioConstraints,
    n_assets: int,
    current_weights: np.ndarray | None = None,
) -> list[dict]:
    """
    Convert PortfolioConstraints to scipy.optimize constraint dicts.

    Returns a list of constraint dicts compatible with scipy SLSQP.
    """
    scipy_cons: list[dict] = []

    if constraints.long_only:
        scipy_cons.append({
            "type": "eq",
            "fun": lambda w: float(np.sum(w) - 1.0),
            "jac": lambda w: np.ones(n_assets),
        })
    else:
        scipy_cons.append({
            "type": "ineq",
            "fun": lambda w: constraints.max_gross_leverage - float(np.sum(np.abs(w))),
        })

    scipy_cons.append({
        "type": "ineq",
        "fun": lambda w: constraints.max_net_exposure - abs(float(np.sum(w))),
    })

    if current_weights is not None and constraints.max_turnover < float("inf"):
        max_to = constraints.max_turnover
        w_curr = current_weights

        scipy_cons.append({
            "type": "ineq",
            "fun": lambda w: max_to - 0.5 * float(np.sum(np.abs(w - w_curr))),
        })

    return scipy_cons


def build_bounds(
    constraints: PortfolioConstraints,
    n_assets: int,
) -> list[tuple[float, float]]:
    """Build per-asset weight bounds for scipy."""
    if constraints.long_only:
        lb = max(0.0, constraints.min_weight)
    else:
        lb = -constraints.max_weight

    return [(lb, constraints.max_weight) for _ in range(n_assets)]


def check_constraints(
    weights: np.ndarray,
    constraints: PortfolioConstraints,
    symbols: list[str] | None = None,
    current_weights: np.ndarray | None = None,
    sector_map: dict[str, str] | None = None,
    tolerance: float = 1e-4,
) -> ConstraintCheckResult:
    """
    Post-optimization constraint validation.

    Returns detailed violation report for audit.
    """
    violations: list[ConstraintViolation] = []
    warnings: list[str] = []
    n = len(weights)

    gross = float(np.sum(np.abs(weights)))
    if gross > constraints.max_gross_leverage + tolerance:
        violations.append(ConstraintViolation(
            "max_gross_leverage", constraints.max_gross_leverage, gross, "hard",
        ))

    net = abs(float(np.sum(weights)))
    if net > constraints.max_net_exposure + tolerance:
        violations.append(ConstraintViolation(
            "max_net_exposure", constraints.max_net_exposure, net, "hard",
        ))

    for i in range(n):
        w = abs(weights[i])
        name = symbols[i] if symbols else f"asset_{i}"
        if w > constraints.max_weight + tolerance:
            violations.append(ConstraintViolation(
                f"max_weight({name})", constraints.max_weight, w, "hard",
            ))
        if constraints.long_only and weights[i] < -tolerance:
            violations.append(ConstraintViolation(
                f"long_only({name})", 0.0, float(weights[i]), "hard",
            ))

    n_active = sum(1 for w in weights if abs(w) > tolerance)
    if n_active < constraints.min_positions and n >= constraints.min_positions:
        violations.append(ConstraintViolation(
            "min_positions", float(constraints.min_positions), float(n_active), "warning",
        ))

    if current_weights is not None:
        turnover = 0.5 * float(np.sum(np.abs(weights - current_weights)))
        if turnover > constraints.max_turnover + tolerance:
            violations.append(ConstraintViolation(
                "max_turnover", constraints.max_turnover, turnover, "warning",
            ))

    if sector_map and symbols:
        sector_w: dict[str, float] = {}
        for i, s in enumerate(symbols):
            sec = sector_map.get(s, "unknown")
            sector_w[sec] = sector_w.get(sec, 0.0) + abs(weights[i])
        for sec, sw in sector_w.items():
            if sw > constraints.max_sector_weight + tolerance:
                violations.append(ConstraintViolation(
                    f"max_sector_weight({sec})",
                    constraints.max_sector_weight, sw, "hard",
                ))

    satisfied = all(v.severity != "hard" for v in violations)
    return ConstraintCheckResult(
        satisfied=satisfied,
        violations=violations,
        warnings=warnings,
    )
