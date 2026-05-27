"""
Capital preservation — the primary objective of institutional risk management.

Capital preservation is not about avoiding all losses — it's about
ensuring that losses are recoverable. A -50% drawdown requires +100%
to recover; a -20% drawdown requires only +25%. The asymmetry of
compounding means that preventing deep drawdowns is more valuable
than capturing marginal gains.

This module computes the leverage multiplier needed to keep the
portfolio within recoverable loss bounds, given current drawdown
and market conditions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from risk_engine.risk_config import DrawdownConfig, RiskRegime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CapitalPreservationState:
    """Capital preservation assessment."""

    max_acceptable_loss: float
    current_drawdown: float
    remaining_risk_budget: float
    recommended_leverage: float
    recovery_required: float
    days_to_recovery_estimate: int | None
    preservation_score: float


class CapitalPreservationEngine:
    """
    Computes dynamic leverage limits based on remaining risk budget.

    As drawdown deepens, the remaining risk budget shrinks, and the
    engine tightens leverage to prevent crossing into irrecoverable
    territory.
    """

    def __init__(
        self,
        config: DrawdownConfig | None = None,
        max_acceptable_total_loss: float = 0.25,
    ) -> None:
        self._config = config or DrawdownConfig()
        self._max_loss = max_acceptable_total_loss

    def assess(
        self,
        current_drawdown: float,
        realized_vol: float,
        risk_regime: RiskRegime = RiskRegime.NORMAL,
    ) -> CapitalPreservationState:
        remaining_budget = self._max_loss - abs(current_drawdown)
        remaining_budget = max(remaining_budget, 0.0)

        if realized_vol > 0 and remaining_budget > 0:
            daily_vol = realized_vol / np.sqrt(252)
            max_lev = remaining_budget / (3.0 * daily_vol)
            max_lev = float(np.clip(max_lev, 0.0, 2.0))
        else:
            max_lev = 0.0

        regime_scale = {
            RiskRegime.NORMAL: 1.0,
            RiskRegime.ELEVATED: 0.8,
            RiskRegime.STRESSED: 0.5,
            RiskRegime.CRISIS: 0.2,
        }[risk_regime]

        recommended = max_lev * regime_scale

        recovery = abs(current_drawdown) / (1.0 - abs(current_drawdown)) if abs(current_drawdown) < 1.0 else float("inf")

        days_est = None
        if realized_vol > 0 and recovery > 0:
            expected_daily = realized_vol / np.sqrt(252) * 0.3
            days_est = int(recovery / max(expected_daily, 1e-6))
            days_est = min(days_est, 9999)

        pres_score = max(0.0, min(1.0, remaining_budget / self._max_loss))

        return CapitalPreservationState(
            max_acceptable_loss=self._max_loss,
            current_drawdown=current_drawdown,
            remaining_risk_budget=remaining_budget,
            recommended_leverage=recommended,
            recovery_required=recovery,
            days_to_recovery_estimate=days_est,
            preservation_score=pres_score,
        )
