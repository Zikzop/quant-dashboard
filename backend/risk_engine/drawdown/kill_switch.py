"""
Kill-switch — staged emergency de-risking, not binary liquidation.

A naive kill-switch that liquidates everything at -20% is destructive:
- It locks in losses at the worst possible time
- It prevents recovery from temporary dislocations
- It creates forced selling in illiquid markets

Instead, we implement staged degradation:
1. Reduce leverage gradually as drawdown deepens
2. Disable unstable alpha groups first (highest recent loss)
3. Increase cash allocation progressively
4. Full halt only at the extreme threshold — and even then,
   close positions over time, not in a single liquidation event.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, unique

import pandas as pd

from risk_engine.risk_config import DrawdownConfig

logger = logging.getLogger(__name__)


@unique
class KillSwitchState(Enum):
    ACTIVE = "ACTIVE"
    REDUCING = "REDUCING"
    HALTED = "HALTED"
    RECOVERING = "RECOVERING"


@dataclass(frozen=True)
class KillSwitchAction:
    """Kill-switch decision output."""

    state: KillSwitchState
    leverage_multiplier: float
    disabled_strategies: tuple[str, ...]
    cash_target: float
    allow_new_trades: bool
    allow_position_increases: bool
    rationale: str
    timestamp: pd.Timestamp


class KillSwitch:
    """
    Staged kill-switch with probabilistic de-risking.

    Rather than a binary on/off, the kill-switch produces a continuous
    leverage multiplier and strategy-level disabling decisions.
    """

    def __init__(self, config: DrawdownConfig | None = None) -> None:
        self._config = config or DrawdownConfig()
        self._state = KillSwitchState.ACTIVE
        self._halt_timestamp: pd.Timestamp | None = None

    @property
    def state(self) -> KillSwitchState:
        return self._state

    def evaluate(
        self,
        current_drawdown: float,
        drawdown_speed: float,
        timestamp: pd.Timestamp,
        strategy_pnls: dict[str, float] | None = None,
    ) -> KillSwitchAction:
        cfg = self._config

        if self._state == KillSwitchState.HALTED:
            if current_drawdown > cfg.kill_switch_threshold + cfg.recovery_buffer_pct:
                days_halted = (
                    (timestamp - self._halt_timestamp).days
                    if self._halt_timestamp else 0
                )
                if days_halted >= cfg.min_recovery_days:
                    self._state = KillSwitchState.RECOVERING
                    return KillSwitchAction(
                        state=KillSwitchState.RECOVERING,
                        leverage_multiplier=0.3,
                        disabled_strategies=(),
                        cash_target=0.50,
                        allow_new_trades=True,
                        allow_position_increases=False,
                        rationale="Recovery phase: cautious re-engagement",
                        timestamp=timestamp,
                    )
            return KillSwitchAction(
                state=KillSwitchState.HALTED,
                leverage_multiplier=0.0,
                disabled_strategies=("ALL",),
                cash_target=1.0,
                allow_new_trades=False,
                allow_position_increases=False,
                rationale=f"Kill-switch active: DD={current_drawdown:.1%}",
                timestamp=timestamp,
            )

        if current_drawdown <= cfg.kill_switch_threshold:
            self._state = KillSwitchState.HALTED
            self._halt_timestamp = timestamp
            logger.critical(
                "KILL SWITCH ACTIVATED: drawdown=%.2f%% at %s",
                current_drawdown * 100,
                timestamp,
            )
            return KillSwitchAction(
                state=KillSwitchState.HALTED,
                leverage_multiplier=0.0,
                disabled_strategies=("ALL",),
                cash_target=1.0,
                allow_new_trades=False,
                allow_position_increases=False,
                rationale=f"Kill-switch triggered: DD={current_drawdown:.1%}",
                timestamp=timestamp,
            )

        if current_drawdown <= cfg.critical_threshold:
            disabled = self._identify_worst_strategies(strategy_pnls, n=3)
            lev = max(0.1, 1.0 + current_drawdown / abs(cfg.critical_threshold) * 0.7)
            self._state = KillSwitchState.REDUCING
            return KillSwitchAction(
                state=KillSwitchState.REDUCING,
                leverage_multiplier=lev,
                disabled_strategies=tuple(disabled),
                cash_target=0.40,
                allow_new_trades=False,
                allow_position_increases=False,
                rationale=f"Critical drawdown: DD={current_drawdown:.1%}, aggressive reduction",
                timestamp=timestamp,
            )

        if current_drawdown <= cfg.reduce_threshold:
            disabled = self._identify_worst_strategies(strategy_pnls, n=1)
            reduction = cfg.leverage_reduction_per_stage
            lev = max(0.3, 1.0 - reduction)
            self._state = KillSwitchState.REDUCING
            return KillSwitchAction(
                state=KillSwitchState.REDUCING,
                leverage_multiplier=lev,
                disabled_strategies=tuple(disabled),
                cash_target=0.25,
                allow_new_trades=True,
                allow_position_increases=False,
                rationale=f"Reducing: DD={current_drawdown:.1%}",
                timestamp=timestamp,
            )

        if self._state == KillSwitchState.RECOVERING:
            if current_drawdown > cfg.warning_threshold:
                self._state = KillSwitchState.ACTIVE
            return KillSwitchAction(
                state=KillSwitchState.RECOVERING,
                leverage_multiplier=0.6,
                disabled_strategies=(),
                cash_target=0.25,
                allow_new_trades=True,
                allow_position_increases=True,
                rationale="Recovering: gradual re-engagement",
                timestamp=timestamp,
            )

        self._state = KillSwitchState.ACTIVE
        return KillSwitchAction(
            state=KillSwitchState.ACTIVE,
            leverage_multiplier=1.0,
            disabled_strategies=(),
            cash_target=0.0,
            allow_new_trades=True,
            allow_position_increases=True,
            rationale="Normal operation",
            timestamp=timestamp,
        )

    @staticmethod
    def _identify_worst_strategies(
        strategy_pnls: dict[str, float] | None,
        n: int,
    ) -> list[str]:
        if not strategy_pnls:
            return []
        sorted_strats = sorted(strategy_pnls.items(), key=lambda x: x[1])
        return [name for name, pnl in sorted_strats[:n] if pnl < 0]
