"""
Drawdown monitor — continuous tracking of peak-to-trough losses.

Tracks multiple drawdown dimensions:
- Portfolio-level drawdown from high water mark
- Strategy-level drawdowns for isolation
- Rolling window drawdowns for regime context
- Speed of drawdown for urgency classification
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from risk_engine.risk_config import DrawdownConfig, RiskRegime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DrawdownState:
    """Current drawdown status."""

    current_drawdown: float
    high_water_mark: float
    current_value: float
    drawdown_duration_days: int
    max_drawdown_trailing: float
    drawdown_speed: float
    drawdown_stage: str
    risk_regime: RiskRegime
    days_since_peak: int


class DrawdownMonitor:
    """
    Monitors portfolio drawdown with staged severity classification.

    Stages:
    - NORMAL: within acceptable drawdown range
    - WARNING: drawdown exceeds warning threshold
    - REDUCE: drawdown requires position reduction
    - CRITICAL: drawdown requires aggressive de-risking
    - KILL: drawdown breaches kill-switch, halt new trading

    The speed of drawdown matters: a -10% drawdown over 3 days is far
    more dangerous than -10% over 60 days (regime shift vs. normal drift).
    """

    def __init__(self, config: DrawdownConfig | None = None) -> None:
        self._config = config or DrawdownConfig()
        self._hwm = 0.0
        self._peak_date: pd.Timestamp | None = None
        self._values: list[tuple[pd.Timestamp, float]] = []

    def update(self, timestamp: pd.Timestamp, portfolio_value: float) -> DrawdownState:
        self._values.append((timestamp, portfolio_value))

        if portfolio_value > self._hwm:
            self._hwm = portfolio_value
            self._peak_date = timestamp

        if self._hwm <= 0:
            dd = 0.0
        else:
            dd = (portfolio_value - self._hwm) / self._hwm

        days_since_peak = 0
        if self._peak_date is not None:
            days_since_peak = max(0, (timestamp - self._peak_date).days)

        trailing_dd = self._trailing_max_drawdown()
        speed = self._drawdown_speed()
        stage = self._classify_stage(dd)
        regime = self._classify_regime(dd, speed)

        return DrawdownState(
            current_drawdown=dd,
            high_water_mark=self._hwm,
            current_value=portfolio_value,
            drawdown_duration_days=days_since_peak,
            max_drawdown_trailing=trailing_dd,
            drawdown_speed=speed,
            drawdown_stage=stage,
            risk_regime=regime,
            days_since_peak=days_since_peak,
        )

    def _classify_stage(self, dd: float) -> str:
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

    def _classify_regime(self, dd: float, speed: float) -> RiskRegime:
        cfg = self._config
        if dd <= cfg.kill_switch_threshold or speed < -0.02:
            return RiskRegime.CRISIS
        elif dd <= cfg.critical_threshold or speed < -0.01:
            return RiskRegime.STRESSED
        elif dd <= cfg.warning_threshold:
            return RiskRegime.ELEVATED
        return RiskRegime.NORMAL

    def _trailing_max_drawdown(self) -> float:
        n = self._config.trailing_window_days
        if len(self._values) < 2:
            return 0.0
        recent = self._values[-n:]
        vals = np.array([v for _, v in recent])
        running_max = np.maximum.accumulate(vals)
        dds = (vals - running_max) / np.maximum(running_max, 1e-9)
        return float(np.min(dds))

    def _drawdown_speed(self) -> float:
        if len(self._values) < 6:
            return 0.0
        recent = [v for _, v in self._values[-5:]]
        if recent[0] <= 0:
            return 0.0
        return (recent[-1] - recent[0]) / recent[0]

    def reset(self) -> None:
        self._hwm = 0.0
        self._peak_date = None
        self._values.clear()
