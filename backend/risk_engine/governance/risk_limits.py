"""
Risk limits — hard and soft constraints for portfolio risk management.

Hard limits are inviolable: breaching them triggers automatic action.
Soft limits are advisory: breaching them generates warnings and requires
acknowledgment but doesn't force action.

Each limit has:
- A metric (what we're measuring)
- A threshold (the boundary)
- A severity (what happens on breach)
- A cooldown (minimum time between re-triggering)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique

import pandas as pd

from risk_engine.risk_config import EscalationLevel

logger = logging.getLogger(__name__)


@unique
class LimitType(Enum):
    HARD = "HARD"
    SOFT = "SOFT"


@dataclass(frozen=True)
class RiskLimit:
    """Definition of a single risk limit."""

    name: str
    metric: str
    threshold: float
    limit_type: LimitType
    escalation_level: EscalationLevel
    direction: str = "upper"
    cooldown_seconds: int = 300
    description: str = ""


@dataclass(frozen=True)
class LimitStatus:
    """Current status of a risk limit."""

    limit: RiskLimit
    current_value: float
    is_breached: bool
    utilization: float
    headroom: float
    breach_severity: float


def build_default_limits() -> list[RiskLimit]:
    """Construct the standard institutional risk limit set."""
    return [
        RiskLimit(
            name="gross_leverage",
            metric="gross_leverage",
            threshold=2.0,
            limit_type=LimitType.HARD,
            escalation_level=EscalationLevel.CRITICAL,
            description="Maximum gross leverage ratio",
        ),
        RiskLimit(
            name="net_exposure",
            metric="net_leverage",
            threshold=1.0,
            limit_type=LimitType.HARD,
            escalation_level=EscalationLevel.CRITICAL,
            description="Maximum absolute net exposure ratio",
        ),
        RiskLimit(
            name="single_name_concentration",
            metric="max_single_name_weight",
            threshold=0.15,
            limit_type=LimitType.HARD,
            escalation_level=EscalationLevel.WARNING,
            description="Maximum single-name position weight",
        ),
        RiskLimit(
            name="hhi_concentration",
            metric="hhi",
            threshold=0.25,
            limit_type=LimitType.SOFT,
            escalation_level=EscalationLevel.WARNING,
            description="HHI concentration threshold",
        ),
        RiskLimit(
            name="portfolio_var_95",
            metric="var_95",
            threshold=-0.02,
            limit_type=LimitType.HARD,
            escalation_level=EscalationLevel.CRITICAL,
            direction="lower",
            description="1-day 95% VaR limit",
        ),
        RiskLimit(
            name="portfolio_var_99",
            metric="var_99",
            threshold=-0.05,
            limit_type=LimitType.HARD,
            escalation_level=EscalationLevel.EMERGENCY,
            direction="lower",
            description="1-day 99% VaR limit",
        ),
        RiskLimit(
            name="max_drawdown",
            metric="drawdown",
            threshold=-0.20,
            limit_type=LimitType.HARD,
            escalation_level=EscalationLevel.EMERGENCY,
            direction="lower",
            description="Maximum drawdown from high water mark",
        ),
        RiskLimit(
            name="drawdown_warning",
            metric="drawdown",
            threshold=-0.10,
            limit_type=LimitType.SOFT,
            escalation_level=EscalationLevel.WARNING,
            direction="lower",
            description="Drawdown warning threshold",
        ),
        RiskLimit(
            name="correlation_regime",
            metric="mean_correlation",
            threshold=0.70,
            limit_type=LimitType.SOFT,
            escalation_level=EscalationLevel.WARNING,
            description="Mean pairwise correlation warning level",
        ),
        RiskLimit(
            name="volatility_spike",
            metric="realized_vol_ratio",
            threshold=2.0,
            limit_type=LimitType.SOFT,
            escalation_level=EscalationLevel.WARNING,
            description="Realized vol / target vol ratio",
        ),
    ]
