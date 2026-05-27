"""
Risk actions — automated responses to governance escalations.

When the governance layer determines that action is needed, this module
translates escalation decisions into concrete portfolio modifications:
- Leverage reduction targets
- Position trimming orders
- Strategy disabling signals
- Cash allocation adjustments

These are recommendations, not direct executions. The execution layer
decides how to implement them given current market conditions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from risk_engine.risk_config import EscalationLevel
from risk_engine.governance.escalation_engine import EscalationAction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskActionOrder:
    """A concrete risk mitigation instruction."""

    action_type: str
    target: str
    magnitude: float
    urgency: str
    rationale: str
    timestamp: pd.Timestamp


class RiskActionEngine:
    """
    Translates escalation actions into concrete portfolio directives.

    The mapping is:
    - CRITICAL leverage breach → reduce leverage to 80% of limit
    - EMERGENCY drawdown breach → halt + staged liquidation
    - WARNING concentration → suggest rebalance
    - VaR breach → reduce to bring VaR within limits
    """

    def __init__(self) -> None:
        self._pending_actions: list[RiskActionOrder] = []

    def generate_actions(
        self,
        escalations: list[EscalationAction],
    ) -> list[RiskActionOrder]:
        actions: list[RiskActionOrder] = []

        for esc in escalations:
            if esc.halt_trading:
                actions.append(RiskActionOrder(
                    action_type="HALT_TRADING",
                    target="ALL",
                    magnitude=1.0,
                    urgency="IMMEDIATE",
                    rationale=esc.message,
                    timestamp=esc.timestamp,
                ))
            elif esc.auto_reduce:
                actions.append(RiskActionOrder(
                    action_type="REDUCE_LEVERAGE",
                    target="PORTFOLIO",
                    magnitude=0.20,
                    urgency="HIGH",
                    rationale=esc.message,
                    timestamp=esc.timestamp,
                ))

            if "concentration" in esc.limit_name:
                actions.append(RiskActionOrder(
                    action_type="REBALANCE",
                    target=esc.limit_name,
                    magnitude=0.10,
                    urgency="MEDIUM",
                    rationale=esc.message,
                    timestamp=esc.timestamp,
                ))

            if "var" in esc.limit_name.lower():
                actions.append(RiskActionOrder(
                    action_type="REDUCE_RISK",
                    target="PORTFOLIO",
                    magnitude=0.15,
                    urgency="HIGH",
                    rationale=esc.message,
                    timestamp=esc.timestamp,
                ))

        self._pending_actions.extend(actions)
        return actions

    @property
    def pending_actions(self) -> list[RiskActionOrder]:
        return list(self._pending_actions)

    def clear_pending(self) -> None:
        self._pending_actions.clear()
