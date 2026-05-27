"""
Live drawdown tracking — real-time drawdown computation for streaming.

Maintains high-water mark and computes drawdown with minimal state
for high-frequency updates. Emits alerts when drawdown crosses
stage boundaries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from risk_engine.risk_config import DrawdownConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveDrawdownUpdate:
    """Streaming drawdown state."""

    timestamp: pd.Timestamp
    current_drawdown: float
    high_water_mark: float
    nav: float
    stage: str
    stage_changed: bool
    previous_stage: str


class LiveDrawdownTracker:
    """
    Lightweight drawdown tracker for real-time updates.

    Emits stage transitions for alert routing. Stages match
    the DrawdownConfig thresholds: NORMAL, WARNING, REDUCE, CRITICAL, KILL.
    """

    def __init__(self, config: DrawdownConfig | None = None) -> None:
        self._config = config or DrawdownConfig()
        self._hwm = 0.0
        self._current_stage = "NORMAL"

    def update(
        self,
        nav: float,
        timestamp: pd.Timestamp,
    ) -> LiveDrawdownUpdate:
        if nav > self._hwm:
            self._hwm = nav

        if self._hwm <= 0:
            dd = 0.0
        else:
            dd = (nav - self._hwm) / self._hwm

        new_stage = self._classify(dd)
        changed = new_stage != self._current_stage
        prev = self._current_stage
        self._current_stage = new_stage

        if changed:
            logger.warning(
                "Drawdown stage change: %s → %s (DD=%.2f%%)",
                prev, new_stage, dd * 100,
            )

        return LiveDrawdownUpdate(
            timestamp=timestamp,
            current_drawdown=dd,
            high_water_mark=self._hwm,
            nav=nav,
            stage=new_stage,
            stage_changed=changed,
            previous_stage=prev,
        )

    def _classify(self, dd: float) -> str:
        cfg = self._config
        if dd <= cfg.kill_switch_threshold:
            return "KILL"
        elif dd <= cfg.critical_threshold:
            return "CRITICAL"
        elif dd <= cfg.reduce_threshold:
            return "REDUCE"
        elif dd <= cfg.warning_threshold:
            return "WARNING"
        return "NORMAL"

    def reset(self, initial_nav: float = 0.0) -> None:
        self._hwm = initial_nav
        self._current_stage = "NORMAL"

    def to_dict(self, update: LiveDrawdownUpdate) -> dict[str, Any]:
        return {
            "timestamp": update.timestamp.isoformat(),
            "drawdown": update.current_drawdown,
            "hwm": update.high_water_mark,
            "nav": update.nav,
            "stage": update.stage,
            "stage_changed": update.stage_changed,
        }
