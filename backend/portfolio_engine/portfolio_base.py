"""
Portfolio engine base types — core data structures for institutional portfolio construction.

All types are immutable dataclasses to prevent accidental mutation during optimization
and allocation pipelines. Mutable state lives only in the orchestrator.

Statistical assumptions:
- Weight vectors represent fractional capital allocation, not share counts.
- Constraints are enforced pre-optimization and post-optimization (double-gate).
- NaN/Inf values are rejected at construction time to prevent silent corruption.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@unique
class OptimizationObjective(Enum):
    MEAN_VARIANCE = "mean_variance"
    MINIMUM_VARIANCE = "minimum_variance"
    RISK_PARITY = "risk_parity"
    HIERARCHICAL_RISK_PARITY = "hierarchical_risk_parity"
    MAX_DIVERSIFICATION = "max_diversification"


@unique
class RebalanceTrigger(Enum):
    PERIODIC = "periodic"
    THRESHOLD = "threshold"
    TURNOVER_AWARE = "turnover_aware"
    TRANSACTION_AWARE = "transaction_aware"


@unique
class SizingMethod(Enum):
    VOLATILITY_TARGET = "volatility_target"
    KELLY = "kelly"
    RISK_BUDGET = "risk_budget"
    INVERSE_VOLATILITY = "inverse_volatility"
    EQUAL_RISK = "equal_risk"


def _validate_finite(value: float, name: str) -> None:
    if not np.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value}")


@dataclass(frozen=True)
class PortfolioConstraints:
    """
    Hard constraints for portfolio construction.

    These are enforced as inequality constraints in the optimizer and as
    post-optimization validation gates. Violations trigger warnings, not
    silent clipping, unless ``enforce_hard`` is True.
    """

    max_gross_leverage: float = 1.0
    max_net_exposure: float = 1.0
    min_weight: float = 0.0
    max_weight: float = 0.25
    max_sector_weight: float = 0.40
    max_turnover: float = 0.50
    min_positions: int = 3
    max_positions: int = 50
    long_only: bool = False
    enforce_hard: bool = True

    def __post_init__(self) -> None:
        _validate_finite(self.max_gross_leverage, "max_gross_leverage")
        _validate_finite(self.max_weight, "max_weight")
        if self.max_weight <= 0:
            raise ValueError(f"max_weight must be positive, got {self.max_weight}")
        if self.min_positions < 1:
            raise ValueError(f"min_positions must be >= 1, got {self.min_positions}")


@dataclass(frozen=True)
class PortfolioWeights:
    """
    Immutable weight vector with validation.

    Weights are fractional capital allocations. Negative weights indicate short positions.
    The sum of absolute weights equals gross leverage.
    """

    weights: dict[str, float]
    timestamp: pd.Timestamp
    method: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for symbol, w in self.weights.items():
            if not np.isfinite(w):
                raise ValueError(f"Weight for {symbol} is not finite: {w}")

    @property
    def gross_leverage(self) -> float:
        return sum(abs(w) for w in self.weights.values())

    @property
    def net_exposure(self) -> float:
        return sum(self.weights.values())

    @property
    def n_positions(self) -> int:
        return sum(1 for w in self.weights.values() if abs(w) > 1e-8)

    @property
    def long_weights(self) -> dict[str, float]:
        return {s: w for s, w in self.weights.items() if w > 1e-8}

    @property
    def short_weights(self) -> dict[str, float]:
        return {s: w for s, w in self.weights.items() if w < -1e-8}

    @property
    def max_absolute_weight(self) -> float:
        if not self.weights:
            return 0.0
        return max(abs(w) for w in self.weights.values())

    def to_series(self) -> pd.Series:
        return pd.Series(self.weights, name="weight")

    def normalized(self, target_leverage: float = 1.0) -> PortfolioWeights:
        gl = self.gross_leverage
        if gl < 1e-12:
            return self
        scale = target_leverage / gl
        return PortfolioWeights(
            weights={s: w * scale for s, w in self.weights.items()},
            timestamp=self.timestamp,
            method=self.method,
            metadata={**self.metadata, "normalized_from": gl},
        )


@dataclass(frozen=True)
class Position:
    """Snapshot of a single position for portfolio construction purposes."""

    symbol: str
    quantity: float
    market_price: float
    market_value: float
    weight: float
    avg_cost: float = 0.0
    unrealized_pnl: float = 0.0
    sector: str = ""
    volatility: float = 0.0

    def __post_init__(self) -> None:
        _validate_finite(self.market_value, f"market_value({self.symbol})")
        _validate_finite(self.weight, f"weight({self.symbol})")


@dataclass(frozen=True)
class PortfolioState:
    """
    Immutable snapshot of full portfolio state for construction/rebalancing decisions.

    This is distinct from backtesting.portfolio.PortfolioState which is mutable
    and tracks execution. This snapshot feeds the optimizer.
    """

    positions: dict[str, Position]
    cash: float
    nav: float
    timestamp: pd.Timestamp
    current_weights: dict[str, float] = field(default_factory=dict)
    returns_history: pd.DataFrame | None = None
    covariance_matrix: pd.DataFrame | None = None

    @property
    def gross_leverage(self) -> float:
        if self.nav <= 0:
            return 0.0
        return sum(abs(p.market_value) for p in self.positions.values()) / self.nav

    @property
    def n_positions(self) -> int:
        return sum(1 for p in self.positions.values() if abs(p.weight) > 1e-8)


@dataclass(frozen=True)
class AllocationResult:
    """
    Output of the portfolio construction pipeline.

    Contains target weights, the delta from current weights (trade list),
    and diagnostic metadata for audit and analysis.
    """

    target_weights: PortfolioWeights
    current_weights: dict[str, float]
    weight_deltas: dict[str, float]
    turnover: float
    expected_risk: float
    expected_return: float
    risk_contributions: dict[str, float]
    method: str
    constraints_satisfied: bool
    constraint_violations: list[str]
    warnings: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_finite(self.turnover, "turnover")
        _validate_finite(self.expected_risk, "expected_risk")

    @property
    def is_valid(self) -> bool:
        return self.constraints_satisfied and len(self.constraint_violations) == 0


def validate_weights_against_constraints(
    weights: PortfolioWeights,
    constraints: PortfolioConstraints,
    sector_map: dict[str, str] | None = None,
) -> list[str]:
    """
    Validate weight vector against portfolio constraints. Returns list of violations.

    This is called both pre- and post-optimization as a safety gate.
    """
    violations: list[str] = []

    if weights.gross_leverage > constraints.max_gross_leverage + 1e-6:
        violations.append(
            f"Gross leverage {weights.gross_leverage:.4f} exceeds "
            f"max {constraints.max_gross_leverage:.4f}"
        )

    if abs(weights.net_exposure) > constraints.max_net_exposure + 1e-6:
        violations.append(
            f"Net exposure {weights.net_exposure:.4f} exceeds "
            f"max {constraints.max_net_exposure:.4f}"
        )

    for symbol, w in weights.weights.items():
        if abs(w) > constraints.max_weight + 1e-6:
            violations.append(
                f"{symbol} weight {w:.4f} exceeds max {constraints.max_weight:.4f}"
            )
        if constraints.long_only and w < -1e-8:
            violations.append(f"{symbol} has short weight {w:.4f} in long-only portfolio")

    if weights.n_positions < constraints.min_positions:
        violations.append(
            f"Only {weights.n_positions} positions, minimum is {constraints.min_positions}"
        )

    if sector_map:
        sector_weights: dict[str, float] = {}
        for s, w in weights.weights.items():
            sec = sector_map.get(s, "unknown")
            sector_weights[sec] = sector_weights.get(sec, 0.0) + abs(w)
        for sec, sw in sector_weights.items():
            if sw > constraints.max_sector_weight + 1e-6:
                violations.append(
                    f"Sector {sec} weight {sw:.4f} exceeds max {constraints.max_sector_weight:.4f}"
                )

    return violations


def compute_turnover(
    current: dict[str, float], target: dict[str, float]
) -> tuple[float, dict[str, float]]:
    """
    Compute one-way turnover and per-asset weight deltas.

    Turnover = 0.5 * sum(|w_target - w_current|) for all assets in union.
    """
    all_symbols = set(current) | set(target)
    deltas = {}
    total = 0.0
    for s in all_symbols:
        delta = target.get(s, 0.0) - current.get(s, 0.0)
        deltas[s] = delta
        total += abs(delta)
    return total / 2.0, deltas
