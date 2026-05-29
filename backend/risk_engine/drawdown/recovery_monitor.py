"""
Recovery monitor — tracks portfolio recovery after drawdowns.

After a significant drawdown, the recovery phase requires different
risk management than normal operation:
- Slower leverage increase to prevent whipsaw
- Monitoring for false recoveries (dead cat bounces)
- Tracking time-to-recovery for strategy evaluation
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from risk_engine.risk_config import DrawdownConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecoveryState:
    """Current recovery status."""

    is_recovering: bool
    drawdown_at_trough: float
    recovery_pct: float
    days_in_recovery: int
    recovery_velocity: float
    estimated_days_to_full: int | None
    false_recovery_risk: float
    recommended_leverage_cap: float


class RecoveryMonitor:
    """
    Tracks recovery progress and constrains re-engagement speed.

    A false recovery (partial bounce followed by new lows) is dangerous
    because it can trigger premature re-leveraging. The monitor tracks
    recovery velocity and computes false-recovery risk based on the
    pattern of the bounce.
    """

    def __init__(self, config: DrawdownConfig | None = None) -> None:
        self._config = config or DrawdownConfig()
        self._trough_drawdown: float = 0.0
        self._trough_date: pd.Timestamp | None = None
        self._recovery_start: pd.Timestamp | None = None
        self._recovering = False
        self._recovery_values: list[float] = []

    def update(
        self,
        current_drawdown: float,
        timestamp: pd.Timestamp,
    ) -> RecoveryState:
        if current_drawdown < self._trough_drawdown:
            self._trough_drawdown = current_drawdown
            self._trough_date = timestamp
            self._recovering = False
            self._recovery_values.clear()

        if (
            not self._recovering
            and self._trough_drawdown < self._config.reduce_threshold
            and current_drawdown > self._trough_drawdown + self._config.recovery_buffer_pct
        ):
            self._recovering = True
            self._recovery_start = timestamp
            self._recovery_values.clear()

        if self._recovering:
            self._recovery_values.append(current_drawdown)

        if current_drawdown >= 0:
            self._recovering = False
            self._trough_drawdown = 0.0
            self._recovery_values.clear()

        if not self._recovering:
            return RecoveryState(
                is_recovering=False,
                drawdown_at_trough=self._trough_drawdown,
                recovery_pct=0.0,
                days_in_recovery=0,
                recovery_velocity=0.0,
                estimated_days_to_full=None,
                false_recovery_risk=0.0,
                recommended_leverage_cap=1.0,
            )

        total_to_recover = abs(self._trough_drawdown)
        recovered = abs(self._trough_drawdown) - abs(current_drawdown)
        recovery_pct = recovered / max(total_to_recover, 1e-9)

        days_in = (
            (timestamp - self._recovery_start).days
            if self._recovery_start else 0
        )

        velocity = recovered / max(days_in, 1)

        est_remaining = None
        if velocity > 0:
            remaining = total_to_recover - recovered
            est_remaining = int(remaining / velocity)
            est_remaining = min(est_remaining, 9999)

        false_risk = self._estimate_false_recovery_risk()

        lev_cap = min(1.0, 0.3 + 0.7 * recovery_pct)

        return RecoveryState(
            is_recovering=True,
            drawdown_at_trough=self._trough_drawdown,
            recovery_pct=recovery_pct,
            days_in_recovery=days_in,
            recovery_velocity=velocity,
            estimated_days_to_full=est_remaining,
            false_recovery_risk=false_risk,
            recommended_leverage_cap=lev_cap,
        )

    def _estimate_false_recovery_risk(self) -> float:
        if len(self._recovery_values) < 3:
            return 0.5
        recent = self._recovery_values[-5:]
        improving = sum(
            1 for i in range(1, len(recent)) if recent[i] > recent[i - 1]
        )
        consistency = improving / max(len(recent) - 1, 1)
        return max(0.0, min(1.0, 1.0 - consistency))
