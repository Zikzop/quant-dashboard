"""
Rebalancing engine — determines when and how to rebalance the portfolio.

Supports multiple trigger modes:
- Periodic: calendar-based (daily, weekly, monthly)
- Threshold: rebalance when drift exceeds tolerance band
- Turnover-aware: suppress rebalancing when turnover cost exceeds benefit
- Transaction-aware: adjust rebalancing for transaction cost drag

Statistical assumptions:
- Drift is measured as Euclidean distance between current and target weights.
- Rebalancing frequency trades off tracking error vs transaction costs.
- Optimal rebalancing frequency depends on vol regime and cost structure.

Known limitations:
- Calendar rebalancing ignores market conditions.
- Threshold rebalancing can trigger excessive turnover in high-vol environments.
- The optimal threshold is not static — should adapt to regime.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique

import numpy as np
import pandas as pd

from portfolio_engine.portfolio_base import compute_turnover

logger = logging.getLogger(__name__)


@unique
class RebalanceFrequency(Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"


@dataclass(frozen=True)
class RebalanceConfig:
    frequency: RebalanceFrequency = RebalanceFrequency.WEEKLY
    drift_threshold: float = 0.05
    min_turnover_threshold: float = 0.01
    max_turnover_per_rebalance: float = 0.30
    suppress_if_cost_exceeds_benefit: bool = True
    cost_benefit_ratio_threshold: float = 0.5
    estimated_cost_bps: float = 10.0


@dataclass(frozen=True)
class RebalanceDecision:
    should_rebalance: bool
    trigger_reason: str
    max_drift: float
    total_turnover: float
    estimated_cost_bps: float
    cost_benefit_assessment: str
    weight_deltas: dict[str, float]
    warnings: list[str] = field(default_factory=list)


class RebalanceEngine:
    """
    Decide whether and how much to rebalance.

    Evaluates drift, calendar, and cost-benefit criteria to produce
    a rebalance decision with full audit trail.
    """

    def __init__(self, config: RebalanceConfig | None = None) -> None:
        self._config = config or RebalanceConfig()
        self._last_rebalance_date: pd.Timestamp | None = None

    def evaluate(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        timestamp: pd.Timestamp,
        estimated_cost_bps: float | None = None,
    ) -> RebalanceDecision:
        cfg = self._config
        warnings: list[str] = []

        turnover, deltas = compute_turnover(current_weights, target_weights)

        per_asset_drift = {
            s: abs(target_weights.get(s, 0.0) - current_weights.get(s, 0.0))
            for s in set(current_weights) | set(target_weights)
        }
        max_drift = max(per_asset_drift.values()) if per_asset_drift else 0.0

        periodic_due = self._check_periodic(timestamp)

        threshold_triggered = max_drift >= cfg.drift_threshold

        too_small = turnover < cfg.min_turnover_threshold
        too_large = turnover > cfg.max_turnover_per_rebalance

        cost_bps = estimated_cost_bps if estimated_cost_bps is not None else cfg.estimated_cost_bps
        total_cost = turnover * cost_bps

        if cfg.suppress_if_cost_exceeds_benefit:
            tracking_error_benefit = max_drift * 10_000
            if tracking_error_benefit > 0:
                cost_ratio = total_cost / tracking_error_benefit
            else:
                cost_ratio = float("inf")
            cost_suppress = cost_ratio > cfg.cost_benefit_ratio_threshold
            cost_assessment = (
                f"cost/benefit ratio = {cost_ratio:.3f} "
                f"({'suppressed' if cost_suppress else 'acceptable'})"
            )
        else:
            cost_suppress = False
            cost_assessment = "cost-benefit check disabled"

        should_rebalance = False
        reason = "no trigger"

        if threshold_triggered and not too_small and not cost_suppress:
            should_rebalance = True
            reason = f"drift threshold exceeded (max_drift={max_drift:.4f})"
        elif periodic_due and not too_small and not cost_suppress:
            should_rebalance = True
            reason = f"periodic rebalance ({cfg.frequency.value})"

        if too_large and should_rebalance:
            warnings.append(
                f"Turnover {turnover:.4f} exceeds max {cfg.max_turnover_per_rebalance:.4f}, "
                "capping deltas"
            )
            scale = cfg.max_turnover_per_rebalance / turnover
            deltas = {s: d * scale for s, d in deltas.items()}
            turnover = cfg.max_turnover_per_rebalance

        if should_rebalance:
            self._last_rebalance_date = timestamp

        return RebalanceDecision(
            should_rebalance=should_rebalance,
            trigger_reason=reason,
            max_drift=max_drift,
            total_turnover=turnover,
            estimated_cost_bps=total_cost,
            cost_benefit_assessment=cost_assessment,
            weight_deltas=deltas,
            warnings=warnings,
        )

    def _check_periodic(self, timestamp: pd.Timestamp) -> bool:
        if self._last_rebalance_date is None:
            return True

        cfg = self._config
        elapsed = (timestamp - self._last_rebalance_date).days

        thresholds = {
            RebalanceFrequency.DAILY: 1,
            RebalanceFrequency.WEEKLY: 5,
            RebalanceFrequency.BIWEEKLY: 10,
            RebalanceFrequency.MONTHLY: 21,
        }
        return elapsed >= thresholds.get(cfg.frequency, 5)
