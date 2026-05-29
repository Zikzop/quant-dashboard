"""
Realtime risk monitor — aggregates all risk signals into a live snapshot.

This is the primary interface for live risk monitoring. It maintains
in-memory state and produces risk snapshots on every update, suitable
for WebSocket streaming to a dashboard.

The monitor is designed to be called on every price tick or at regular
intervals (e.g., every second for intraday, every bar for daily).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from risk_engine.risk_config import RiskRegime, RiskEngineConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskSnapshot:
    """Complete point-in-time risk state for dashboard consumption."""

    timestamp: pd.Timestamp
    nav: float
    gross_leverage: float
    net_leverage: float
    current_drawdown: float
    drawdown_stage: str
    kill_switch_state: str
    var_95: float
    var_99: float
    cvar_95: float
    realized_vol: float
    target_leverage: float
    mean_correlation: float
    concentration_hhi: float
    risk_regime: RiskRegime
    n_breaches: int
    active_warnings: tuple[str, ...]
    portfolio_risk_score: float


class RealtimeRiskMonitor:
    """
    Produces live risk snapshots by aggregating component signals.

    Maintains a rolling buffer of recent snapshots for trend analysis
    and exposes a serializable snapshot format compatible with WebSocket
    streaming.
    """

    def __init__(
        self,
        config: RiskEngineConfig | None = None,
        max_history: int = 10_000,
    ) -> None:
        self._config = config or RiskEngineConfig()
        self._max_history = max_history
        self._snapshots: list[RiskSnapshot] = []

    def update(
        self,
        timestamp: pd.Timestamp,
        nav: float,
        gross_leverage: float = 0.0,
        net_leverage: float = 0.0,
        drawdown: float = 0.0,
        drawdown_stage: str = "NORMAL",
        kill_switch_state: str = "ACTIVE",
        var_95: float = 0.0,
        var_99: float = 0.0,
        cvar_95: float = 0.0,
        realized_vol: float = 0.0,
        target_leverage: float = 1.0,
        mean_correlation: float = 0.0,
        concentration_hhi: float = 0.0,
        risk_regime: RiskRegime = RiskRegime.NORMAL,
        n_breaches: int = 0,
        warnings: list[str] | None = None,
    ) -> RiskSnapshot:
        risk_score = self._compute_risk_score(
            drawdown=drawdown,
            var_99=var_99,
            gross_leverage=gross_leverage,
            mean_correlation=mean_correlation,
            realized_vol=realized_vol,
        )

        snapshot = RiskSnapshot(
            timestamp=timestamp,
            nav=nav,
            gross_leverage=gross_leverage,
            net_leverage=net_leverage,
            current_drawdown=drawdown,
            drawdown_stage=drawdown_stage,
            kill_switch_state=kill_switch_state,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            realized_vol=realized_vol,
            target_leverage=target_leverage,
            mean_correlation=mean_correlation,
            concentration_hhi=concentration_hhi,
            risk_regime=risk_regime,
            n_breaches=n_breaches,
            active_warnings=tuple(warnings or []),
            portfolio_risk_score=risk_score,
        )

        self._snapshots.append(snapshot)
        if len(self._snapshots) > self._max_history:
            self._snapshots = self._snapshots[-self._max_history:]

        return snapshot

    @property
    def latest(self) -> RiskSnapshot | None:
        return self._snapshots[-1] if self._snapshots else None

    @property
    def history(self) -> list[RiskSnapshot]:
        return list(self._snapshots)

    def to_dict(self, snapshot: RiskSnapshot | None = None) -> dict[str, Any]:
        """Serialize snapshot for WebSocket / JSON transmission."""
        s = snapshot or self.latest
        if s is None:
            return {}
        return {
            "timestamp": s.timestamp.isoformat(),
            "nav": s.nav,
            "gross_leverage": s.gross_leverage,
            "net_leverage": s.net_leverage,
            "drawdown": s.current_drawdown,
            "drawdown_stage": s.drawdown_stage,
            "kill_switch": s.kill_switch_state,
            "var_95": s.var_95,
            "var_99": s.var_99,
            "cvar_95": s.cvar_95,
            "realized_vol": s.realized_vol,
            "target_leverage": s.target_leverage,
            "mean_correlation": s.mean_correlation,
            "hhi": s.concentration_hhi,
            "risk_regime": s.risk_regime.value,
            "n_breaches": s.n_breaches,
            "warnings": list(s.active_warnings),
            "risk_score": s.portfolio_risk_score,
        }

    @staticmethod
    def _compute_risk_score(
        drawdown: float,
        var_99: float,
        gross_leverage: float,
        mean_correlation: float,
        realized_vol: float,
    ) -> float:
        """
        Composite risk score 0-100 (higher = more risk).

        Blends multiple risk dimensions into a single headline number
        for dashboard display. NOT a statistical measure — a heuristic
        summary for quick situational awareness.
        """
        dd_score = min(100, abs(drawdown) / 0.20 * 100)
        var_score = min(100, abs(var_99) / 0.05 * 100)
        lev_score = min(100, gross_leverage / 2.0 * 100)
        corr_score = min(100, mean_correlation / 0.8 * 100)
        vol_score = min(100, realized_vol / 0.40 * 100)

        composite = (
            0.30 * dd_score
            + 0.25 * var_score
            + 0.20 * lev_score
            + 0.15 * corr_score
            + 0.10 * vol_score
        )
        return min(100.0, max(0.0, composite))
