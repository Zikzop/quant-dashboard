"""
Liquidity stress testing — what if you can't exit positions?

Liquidity risk is invisible until it materializes. Positions that
trade freely in normal markets can become illiquid in crises when:
- Bid-ask spreads widen 5-10x
- Market depth evaporates
- Forced sellers overwhelm available liquidity
- Counterparty risk freezes credit markets

This module estimates the cost of emergency liquidation and the
time required to unwind positions without excessive market impact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiquidityProfile:
    """Per-position liquidity characteristics."""

    symbol: str
    avg_daily_volume: float
    position_size: float
    days_to_liquidate: float
    liquidation_cost_pct: float
    liquidity_score: float


@dataclass(frozen=True)
class LiquidityStressResult:
    """Portfolio-level liquidity stress assessment."""

    total_liquidation_cost: float
    weighted_days_to_liquidate: float
    illiquid_weight: float
    worst_position: str
    worst_days: float
    portfolio_liquidity_score: float
    positions: tuple[LiquidityProfile, ...]
    stress_liquidation_cost: float


class LiquidityStressEngine:
    """
    Estimates liquidation costs under normal and stressed conditions.

    The stress multiplier captures the empirical fact that liquidity
    deteriorates precisely when you need it most: spreads widen,
    depth drops, and impact costs spike during market stress.

    The Almgren-Chriss framework implies liquidation cost scales
    as sqrt(urgency / liquidity). More urgent liquidation = higher cost.
    """

    def __init__(
        self,
        participation_rate: float = 0.10,
        impact_coefficient: float = 0.1,
        stress_liquidity_multiplier: float = 3.0,
        spread_stress_multiplier: float = 5.0,
    ) -> None:
        self._participation = participation_rate
        self._impact_coeff = impact_coefficient
        self._stress_liq_mult = stress_liquidity_multiplier
        self._stress_spread_mult = spread_stress_multiplier

    def assess(
        self,
        positions: dict[str, float],
        prices: dict[str, float],
        avg_volumes: dict[str, float],
        nav: float,
        spreads_bps: dict[str, float] | None = None,
    ) -> LiquidityStressResult:
        if not positions or nav <= 0:
            return LiquidityStressResult(
                total_liquidation_cost=0.0,
                weighted_days_to_liquidate=0.0,
                illiquid_weight=0.0,
                worst_position="N/A",
                worst_days=0.0,
                portfolio_liquidity_score=1.0,
                positions=(),
                stress_liquidation_cost=0.0,
            )

        profiles: list[LiquidityProfile] = []
        total_cost = 0.0
        stress_cost = 0.0
        total_abs_value = 0.0
        weighted_days = 0.0

        for symbol, qty in positions.items():
            if qty == 0.0:
                continue

            price = prices.get(symbol, 0.0)
            abs_value = abs(qty * price)
            weight = abs_value / nav
            volume = avg_volumes.get(symbol, 1e6)
            spread = (spreads_bps or {}).get(symbol, 5.0)

            daily_capacity = volume * price * self._participation
            days_to_liq = abs_value / max(daily_capacity, 1e-6)

            impact = self._impact_coeff * np.sqrt(abs_value / max(volume * price, 1e-6))
            spread_cost = spread / 10_000.0
            liq_cost = impact + spread_cost

            stress_impact = impact * self._stress_liq_mult
            stress_spread = spread_cost * self._stress_spread_mult
            stress_pos_cost = stress_impact + stress_spread

            score = float(np.clip(1.0 - days_to_liq / 10.0, 0.0, 1.0))

            profiles.append(LiquidityProfile(
                symbol=symbol,
                avg_daily_volume=volume,
                position_size=abs_value,
                days_to_liquidate=days_to_liq,
                liquidation_cost_pct=liq_cost,
                liquidity_score=score,
            ))

            total_cost += abs_value * liq_cost
            stress_cost += abs_value * stress_pos_cost
            weighted_days += days_to_liq * weight
            total_abs_value += abs_value

        illiquid = sum(p.position_size for p in profiles if p.days_to_liquidate > 3.0)
        illiquid_w = illiquid / max(total_abs_value, 1e-9)

        worst = max(profiles, key=lambda p: p.days_to_liquidate) if profiles else None
        port_score = float(np.mean([p.liquidity_score for p in profiles])) if profiles else 1.0

        return LiquidityStressResult(
            total_liquidation_cost=total_cost / max(nav, 1e-9),
            weighted_days_to_liquidate=weighted_days,
            illiquid_weight=illiquid_w,
            worst_position=worst.symbol if worst else "N/A",
            worst_days=worst.days_to_liquidate if worst else 0.0,
            portfolio_liquidity_score=port_score,
            positions=tuple(profiles),
            stress_liquidation_cost=stress_cost / max(nav, 1e-9),
        )
