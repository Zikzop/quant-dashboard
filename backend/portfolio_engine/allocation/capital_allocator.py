"""
Capital allocation across strategies and alpha signals.

Determines how total portfolio capital is distributed among competing
alpha strategies based on their risk-adjusted performance, capacity,
and current risk budget utilization.

Statistical assumptions:
- Strategy returns are sufficiently independent for diversification benefit.
- Performance persistence is regime-dependent — allocations should adapt.
- Capacity constraints are respected: oversized allocations degrade performance.

Known limitations:
- Allocation is based on historical performance which may not persist.
- Strategy correlations are not stable — diversification can break down.
- Does not model cross-strategy interaction effects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapitalAllocationConfig:
    min_strategy_weight: float = 0.05
    max_strategy_weight: float = 0.40
    performance_lookback_days: int = 252
    ewm_halflife: int = 60
    min_sharpe_threshold: float = 0.0
    capacity_penalty_exponent: float = 0.5
    reallocation_damping: float = 0.3


@dataclass(frozen=True)
class StrategyAllocation:
    strategy_name: str
    weight: float
    risk_budget: float
    sharpe_estimate: float
    capacity_utilization: float


@dataclass(frozen=True)
class CapitalAllocationResult:
    allocations: list[StrategyAllocation]
    total_allocated: float
    unallocated_fraction: float
    effective_n_strategies: float
    warnings: list[str] = field(default_factory=list)


class CapitalAllocator:
    """
    Allocate capital across strategies using risk-adjusted performance weighting.

    Uses a modified inverse-variance approach where weights are proportional to
    Sharpe ratio / volatility, with capacity constraints and damping.
    """

    def __init__(self, config: CapitalAllocationConfig | None = None) -> None:
        self._config = config or CapitalAllocationConfig()

    def allocate(
        self,
        strategy_returns: dict[str, pd.Series],
        current_allocations: dict[str, float] | None = None,
        capacity_limits: dict[str, float] | None = None,
    ) -> CapitalAllocationResult:
        cfg = self._config
        warnings: list[str] = []

        if not strategy_returns:
            return CapitalAllocationResult(
                allocations=[], total_allocated=0.0,
                unallocated_fraction=1.0, effective_n_strategies=0.0,
                warnings=["No strategies provided"],
            )

        scores: dict[str, float] = {}
        sharpes: dict[str, float] = {}

        for name, returns in strategy_returns.items():
            clean = returns.dropna().iloc[-cfg.performance_lookback_days:]
            if len(clean) < 20:
                warnings.append(f"Strategy {name}: insufficient history ({len(clean)} < 20)")
                continue

            ewm = clean.ewm(halflife=cfg.ewm_halflife, min_periods=20)
            mu = float(ewm.mean().iloc[-1]) * 252
            sigma = float(ewm.std().iloc[-1]) * np.sqrt(252)

            if sigma < 1e-8:
                warnings.append(f"Strategy {name}: near-zero volatility, skipping")
                continue

            sharpe = mu / sigma
            sharpes[name] = sharpe

            if sharpe < cfg.min_sharpe_threshold:
                scores[name] = 0.0
            else:
                scores[name] = max(sharpe, 0.0) / sigma

        if not scores or sum(scores.values()) < 1e-12:
            n = len(strategy_returns)
            equal = 1.0 / n if n > 0 else 0.0
            warnings.append("All strategy scores near zero, falling back to equal weight")
            allocations = [
                StrategyAllocation(
                    strategy_name=name, weight=equal, risk_budget=equal,
                    sharpe_estimate=sharpes.get(name, 0.0), capacity_utilization=0.0,
                )
                for name in strategy_returns
            ]
            return CapitalAllocationResult(
                allocations=allocations, total_allocated=1.0,
                unallocated_fraction=0.0,
                effective_n_strategies=float(n),
                warnings=warnings,
            )

        total_score = sum(scores.values())
        raw_weights = {name: s / total_score for name, s in scores.items()}

        for name in raw_weights:
            raw_weights[name] = np.clip(
                raw_weights[name], cfg.min_strategy_weight, cfg.max_strategy_weight
            )

        if capacity_limits:
            for name, cap in capacity_limits.items():
                if name in raw_weights and raw_weights[name] > cap:
                    raw_weights[name] = cap
                    warnings.append(f"Strategy {name} capped at capacity limit {cap:.3f}")

        w_sum = sum(raw_weights.values())
        if w_sum > 1e-12:
            raw_weights = {n: w / w_sum for n, w in raw_weights.items()}

        if current_allocations:
            damped = {}
            for name in raw_weights:
                curr = current_allocations.get(name, 0.0)
                damped[name] = curr + cfg.reallocation_damping * (raw_weights[name] - curr)
            raw_weights = damped
            w_sum = sum(raw_weights.values())
            if w_sum > 1e-12:
                raw_weights = {n: w / w_sum for n, w in raw_weights.items()}

        for name in strategy_returns:
            if name not in raw_weights:
                raw_weights[name] = 0.0

        weights_arr = np.array(list(raw_weights.values()))
        hhi = float(np.sum(weights_arr ** 2))
        eff_n = 1.0 / hhi if hhi > 1e-12 else 0.0

        allocations = []
        for name, w in raw_weights.items():
            cap_util = w / capacity_limits[name] if capacity_limits and name in capacity_limits else 0.0
            allocations.append(StrategyAllocation(
                strategy_name=name,
                weight=w,
                risk_budget=w,
                sharpe_estimate=sharpes.get(name, 0.0),
                capacity_utilization=cap_util,
            ))

        total = sum(a.weight for a in allocations)

        return CapitalAllocationResult(
            allocations=allocations,
            total_allocated=total,
            unallocated_fraction=max(0.0, 1.0 - total),
            effective_n_strategies=eff_n,
            warnings=warnings,
        )
