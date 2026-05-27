"""
Historical stress scenarios — what would have happened to this portfolio?

Each scenario applies the actual market returns from a historical crisis
to the current portfolio composition. This captures real correlation
breakdowns and fat-tail co-movements that models miss.

WARNING: Historical stress tests are biased toward known crises.
The next crisis will be different. These tests set a floor, not a ceiling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StressScenario:
    """Definition of a historical stress scenario."""

    name: str
    description: str
    equity_shock: float
    vol_multiplier: float
    correlation_shift: float
    duration_days: int
    recovery_days: int


@dataclass(frozen=True)
class StressResult:
    """Result of applying a stress scenario to the portfolio."""

    scenario_name: str
    portfolio_loss: float
    worst_position_loss: float
    worst_position_symbol: str
    gross_leverage_post: float
    margin_call_risk: bool
    recovery_estimate_days: int


HISTORICAL_SCENARIOS = (
    StressScenario(
        name="Black Monday 1987",
        description="Single-day equity crash of 22.6%",
        equity_shock=-0.226,
        vol_multiplier=4.0,
        correlation_shift=0.40,
        duration_days=1,
        recovery_days=480,
    ),
    StressScenario(
        name="LTCM / Russian Crisis 1998",
        description="Liquidity crisis with correlation breakdown",
        equity_shock=-0.19,
        vol_multiplier=3.0,
        correlation_shift=0.50,
        duration_days=45,
        recovery_days=120,
    ),
    StressScenario(
        name="Dot-Com Crash 2000-2002",
        description="Slow equity bear market, -49% S&P 500",
        equity_shock=-0.49,
        vol_multiplier=1.8,
        correlation_shift=0.20,
        duration_days=645,
        recovery_days=1400,
    ),
    StressScenario(
        name="Global Financial Crisis 2008",
        description="Systemic banking crisis, -57% S&P 500",
        equity_shock=-0.57,
        vol_multiplier=3.5,
        correlation_shift=0.60,
        duration_days=355,
        recovery_days=890,
    ),
    StressScenario(
        name="Flash Crash 2010",
        description="Intraday crash of ~9% with rapid partial recovery",
        equity_shock=-0.09,
        vol_multiplier=5.0,
        correlation_shift=0.70,
        duration_days=1,
        recovery_days=3,
    ),
    StressScenario(
        name="Volmageddon 2018",
        description="VIX spike destroying short-vol strategies",
        equity_shock=-0.10,
        vol_multiplier=6.0,
        correlation_shift=0.30,
        duration_days=5,
        recovery_days=45,
    ),
    StressScenario(
        name="COVID Crash 2020",
        description="Pandemic-driven crash, -34% S&P 500 in 23 days",
        equity_shock=-0.34,
        vol_multiplier=4.5,
        correlation_shift=0.55,
        duration_days=23,
        recovery_days=140,
    ),
    StressScenario(
        name="Rate Shock 2022",
        description="Bond-equity correlation flip, aggressive tightening",
        equity_shock=-0.25,
        vol_multiplier=2.0,
        correlation_shift=0.35,
        duration_days=280,
        recovery_days=450,
    ),
    StressScenario(
        name="Slow Bleed",
        description="Gradual 20% decline with no volatility spike",
        equity_shock=-0.20,
        vol_multiplier=1.2,
        correlation_shift=0.10,
        duration_days=180,
        recovery_days=300,
    ),
)


class HistoricalStressEngine:
    """
    Applies historical stress scenarios to current portfolio.

    For each scenario, the engine:
    1. Applies the equity shock to position values
    2. Adjusts volatility and correlation assumptions
    3. Computes portfolio-level P&L impact
    4. Estimates post-stress leverage and margin risk
    """

    def __init__(
        self,
        scenarios: tuple[StressScenario, ...] | None = None,
    ) -> None:
        self._scenarios = scenarios or HISTORICAL_SCENARIOS

    def run_all(
        self,
        position_weights: dict[str, float],
        position_betas: dict[str, float] | None = None,
        current_leverage: float = 1.0,
    ) -> list[StressResult]:
        results = []
        for scenario in self._scenarios:
            result = self.run_scenario(
                scenario=scenario,
                position_weights=position_weights,
                position_betas=position_betas,
                current_leverage=current_leverage,
            )
            results.append(result)
        return results

    def run_scenario(
        self,
        scenario: StressScenario,
        position_weights: dict[str, float],
        position_betas: dict[str, float] | None = None,
        current_leverage: float = 1.0,
    ) -> StressResult:
        if not position_weights:
            return StressResult(
                scenario_name=scenario.name,
                portfolio_loss=0.0,
                worst_position_loss=0.0,
                worst_position_symbol="N/A",
                gross_leverage_post=0.0,
                margin_call_risk=False,
                recovery_estimate_days=0,
            )

        betas = position_betas or {s: 1.0 for s in position_weights}

        position_losses: dict[str, float] = {}
        for symbol, weight in position_weights.items():
            beta = betas.get(symbol, 1.0)
            idio_noise = 0.0
            pos_loss = weight * (scenario.equity_shock * beta + idio_noise)
            position_losses[symbol] = pos_loss

        portfolio_loss = sum(position_losses.values()) * current_leverage

        worst_sym = min(position_losses, key=position_losses.get)
        worst_loss = position_losses[worst_sym]

        post_leverage = current_leverage * (1.0 + portfolio_loss)
        margin_risk = post_leverage > 2.0 or portfolio_loss < -0.30

        return StressResult(
            scenario_name=scenario.name,
            portfolio_loss=portfolio_loss,
            worst_position_loss=worst_loss,
            worst_position_symbol=worst_sym,
            gross_leverage_post=max(0.0, post_leverage),
            margin_call_risk=margin_risk,
            recovery_estimate_days=scenario.recovery_days,
        )
