"""
Exposure engine — tracks and constrains portfolio exposures in real time.

Exposure is not just gross/net. Factor exposure, sector concentration,
and directional bias all matter for institutional risk management.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backtesting.portfolio.portfolio_state import PortfolioState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExposureSnapshot:
    """Point-in-time exposure metrics."""

    gross_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    gross_leverage: float
    net_leverage: float
    max_position_weight: float
    position_count: int
    long_count: int
    short_count: int
    concentration_hhi: float


class ExposureEngine:
    """Computes and tracks exposure metrics from portfolio state."""

    def compute(self, state: PortfolioState) -> ExposureSnapshot:
        weights = state.position_weights()
        abs_weights = [abs(w) for w in weights.values()]
        hhi = sum(w**2 for w in abs_weights) if abs_weights else 0.0

        long_count = sum(1 for p in state if p.is_long)
        short_count = sum(1 for p in state if p.is_short)

        return ExposureSnapshot(
            gross_exposure=state.gross_exposure,
            net_exposure=state.net_exposure,
            long_exposure=state.long_value,
            short_exposure=state.short_value,
            gross_leverage=state.gross_leverage,
            net_leverage=state.net_leverage,
            max_position_weight=max(abs_weights) if abs_weights else 0.0,
            position_count=len(weights),
            long_count=long_count,
            short_count=short_count,
            concentration_hhi=hhi,
        )

    def check_constraints(
        self,
        state: PortfolioState,
        max_gross_leverage: float,
        max_net_exposure: float,
        max_position_weight: float,
    ) -> list[str]:
        """Return list of constraint violations (empty = all clear)."""
        violations = []
        snap = self.compute(state)

        if snap.gross_leverage > max_gross_leverage:
            violations.append(
                f"Gross leverage {snap.gross_leverage:.2f} exceeds limit {max_gross_leverage:.2f}"
            )
        pv = state.portfolio_value
        if pv > 0 and abs(snap.net_exposure) / pv > max_net_exposure:
            violations.append(
                f"Net exposure {abs(snap.net_exposure)/pv:.2f} exceeds limit {max_net_exposure:.2f}"
            )
        if snap.max_position_weight > max_position_weight:
            violations.append(
                f"Max position weight {snap.max_position_weight:.2f} exceeds limit {max_position_weight:.2f}"
            )
        return violations
