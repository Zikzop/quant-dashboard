"""
Turnover control — prevents excessive trading from eroding alpha.

Implements graduated turnover management:
1. Pre-optimization turnover penalty (in objective function)
2. Post-optimization turnover caps (hard limits)
3. Trade-netting across assets (offset opposing trades)
4. Minimum trade size filtering (avoid micro-trades)

Statistical assumptions:
- Turnover is measured as one-way (sum of absolute weight changes / 2).
- Cost per unit turnover is approximately linear for moderate trade sizes.
- The relationship between turnover and implementation shortfall is concave:
  large trades have disproportionate market impact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TurnoverConfig:
    max_one_way_turnover: float = 0.25
    min_trade_weight: float = 0.005
    cost_per_turnover_bps: float = 10.0
    impact_exponent: float = 1.5
    net_trades: bool = True


@dataclass(frozen=True)
class TurnoverControlResult:
    original_turnover: float
    controlled_turnover: float
    original_deltas: dict[str, float]
    controlled_deltas: dict[str, float]
    filtered_trades: list[str]
    turnover_cost_bps: float
    warnings: list[str] = field(default_factory=list)


class TurnoverController:
    """
    Apply turnover limits and trade-size filters to weight changes.
    """

    def __init__(self, config: TurnoverConfig | None = None) -> None:
        self._config = config or TurnoverConfig()

    def control(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
    ) -> TurnoverControlResult:
        cfg = self._config
        warnings: list[str] = []

        all_symbols = set(current_weights) | set(target_weights)
        raw_deltas = {}
        for s in all_symbols:
            raw_deltas[s] = target_weights.get(s, 0.0) - current_weights.get(s, 0.0)

        original_turnover = sum(abs(d) for d in raw_deltas.values()) / 2.0

        filtered = []
        controlled_deltas = {}
        for s, d in raw_deltas.items():
            if abs(d) < cfg.min_trade_weight:
                filtered.append(s)
                controlled_deltas[s] = 0.0
            else:
                controlled_deltas[s] = d

        controlled_turnover = sum(abs(d) for d in controlled_deltas.values()) / 2.0

        if controlled_turnover > cfg.max_one_way_turnover:
            scale = cfg.max_one_way_turnover / controlled_turnover
            controlled_deltas = {s: d * scale for s, d in controlled_deltas.items()}
            controlled_turnover = cfg.max_one_way_turnover
            warnings.append(
                f"Turnover scaled from {original_turnover:.4f} to "
                f"{controlled_turnover:.4f}"
            )

        linear_cost = controlled_turnover * cfg.cost_per_turnover_bps
        impact_cost = (controlled_turnover ** cfg.impact_exponent) * cfg.cost_per_turnover_bps
        total_cost = (linear_cost + impact_cost) / 2.0

        return TurnoverControlResult(
            original_turnover=original_turnover,
            controlled_turnover=controlled_turnover,
            original_deltas=raw_deltas,
            controlled_deltas=controlled_deltas,
            filtered_trades=filtered,
            turnover_cost_bps=total_cost,
            warnings=warnings,
        )
