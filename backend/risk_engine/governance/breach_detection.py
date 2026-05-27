"""
Breach detection — evaluates current risk state against all limits.

The breach detector takes a dict of metric values and evaluates each
registered risk limit, producing breach reports with severity scoring
and utilization tracking.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from risk_engine.governance.risk_limits import RiskLimit, LimitType, LimitStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BreachReport:
    """Summary of all limit evaluations."""

    timestamp: pd.Timestamp
    total_limits: int
    n_breached: int
    n_hard_breached: int
    n_soft_breached: int
    breached_limits: tuple[LimitStatus, ...]
    all_statuses: tuple[LimitStatus, ...]
    max_severity: float
    requires_immediate_action: bool


class BreachDetector:
    """
    Evaluates current risk metrics against all configured limits.

    For each limit, computes:
    - is_breached: whether the threshold is exceeded
    - utilization: current value as fraction of threshold (1.0 = at limit)
    - headroom: remaining capacity before breach
    - severity: how far past the threshold (0 = no breach)
    """

    def __init__(self, limits: list[RiskLimit] | None = None) -> None:
        from risk_engine.governance.risk_limits import build_default_limits
        self._limits = limits or build_default_limits()

    def evaluate(
        self,
        metrics: dict[str, float],
        timestamp: pd.Timestamp,
    ) -> BreachReport:
        statuses: list[LimitStatus] = []
        breached: list[LimitStatus] = []

        for limit in self._limits:
            value = metrics.get(limit.metric, 0.0)
            status = self._check_limit(limit, value)
            statuses.append(status)
            if status.is_breached:
                breached.append(status)

        n_hard = sum(1 for s in breached if s.limit.limit_type == LimitType.HARD)
        n_soft = sum(1 for s in breached if s.limit.limit_type == LimitType.SOFT)
        max_sev = max((s.breach_severity for s in breached), default=0.0)

        return BreachReport(
            timestamp=timestamp,
            total_limits=len(self._limits),
            n_breached=len(breached),
            n_hard_breached=n_hard,
            n_soft_breached=n_soft,
            breached_limits=tuple(breached),
            all_statuses=tuple(statuses),
            max_severity=max_sev,
            requires_immediate_action=n_hard > 0,
        )

    @staticmethod
    def _check_limit(limit: RiskLimit, value: float) -> LimitStatus:
        if limit.direction == "lower":
            is_breached = value < limit.threshold
            utilization = value / min(limit.threshold, -1e-9) if limit.threshold < 0 else 0.0
            headroom = value - limit.threshold
            severity = max(0.0, (limit.threshold - value) / max(abs(limit.threshold), 1e-9))
        else:
            is_breached = value > limit.threshold
            utilization = value / max(limit.threshold, 1e-9)
            headroom = limit.threshold - value
            severity = max(0.0, (value - limit.threshold) / max(abs(limit.threshold), 1e-9))

        return LimitStatus(
            limit=limit,
            current_value=value,
            is_breached=is_breached,
            utilization=utilization,
            headroom=headroom,
            breach_severity=severity,
        )
