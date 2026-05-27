"""
Escalation engine — routes breaches to appropriate response handlers.

Escalation follows a hierarchy:
INFO → log and continue
WARNING → alert risk team, increase monitoring frequency
CRITICAL → trigger automatic risk reduction, require acknowledgment
EMERGENCY → activate kill-switch, halt all new trading

The engine maintains cooldown state to prevent alert fatigue from
rapid re-triggering of the same breach.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

from risk_engine.risk_config import EscalationLevel
from risk_engine.governance.breach_detection import BreachReport, LimitStatus

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EscalationAction:
    """Action triggered by an escalation."""

    level: EscalationLevel
    limit_name: str
    message: str
    auto_reduce: bool
    halt_trading: bool
    require_ack: bool
    timestamp: pd.Timestamp


class EscalationEngine:
    """
    Routes breach events to appropriate risk responses.

    Maintains per-limit cooldown tracking to prevent alert fatigue.
    Critical and emergency escalations bypass cooldown.
    """

    def __init__(self, cooldown_seconds: int = 300) -> None:
        self._cooldown = cooldown_seconds
        self._last_escalation: dict[str, pd.Timestamp] = {}

    def process(
        self,
        breach_report: BreachReport,
    ) -> list[EscalationAction]:
        actions: list[EscalationAction] = []

        for status in breach_report.breached_limits:
            limit = status.limit
            name = limit.name

            if limit.escalation_level in (EscalationLevel.CRITICAL, EscalationLevel.EMERGENCY):
                pass
            elif name in self._last_escalation:
                elapsed = (
                    breach_report.timestamp - self._last_escalation[name]
                ).total_seconds()
                if elapsed < self._cooldown:
                    continue

            action = self._build_action(status, breach_report.timestamp)
            actions.append(action)
            self._last_escalation[name] = breach_report.timestamp

            log_method = {
                EscalationLevel.INFO: logger.info,
                EscalationLevel.WARNING: logger.warning,
                EscalationLevel.CRITICAL: logger.error,
                EscalationLevel.EMERGENCY: logger.critical,
            }.get(limit.escalation_level, logger.warning)
            log_method("RISK ESCALATION [%s]: %s", limit.escalation_level.value, action.message)

        return actions

    @staticmethod
    def _build_action(
        status: LimitStatus,
        timestamp: pd.Timestamp,
    ) -> EscalationAction:
        limit = status.limit
        level = limit.escalation_level

        msg = (
            f"{limit.name}: value={status.current_value:.4f} "
            f"threshold={limit.threshold:.4f} "
            f"severity={status.breach_severity:.2f}"
        )

        return EscalationAction(
            level=level,
            limit_name=limit.name,
            message=msg,
            auto_reduce=level in (EscalationLevel.CRITICAL, EscalationLevel.EMERGENCY),
            halt_trading=level == EscalationLevel.EMERGENCY,
            require_ack=level in (EscalationLevel.CRITICAL, EscalationLevel.EMERGENCY),
            timestamp=timestamp,
        )
