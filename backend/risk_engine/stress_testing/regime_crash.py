"""
Regime crash simulation — what happens when the regime shifts suddenly?

The most dangerous market events are regime transitions:
- Vol regime shift (calm → crisis in days)
- Correlation regime shift (diversified → correlated in hours)
- Liquidity regime shift (liquid → frozen overnight)

This module simulates abrupt regime transitions and computes
their impact on the current portfolio, accounting for the
compounding effect of rising volatility + rising correlation
+ declining liquidity simultaneously.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from risk_engine.risk_config import RiskRegime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegimeCrashScenario:
    """Regime transition specification."""

    name: str
    from_regime: RiskRegime
    to_regime: RiskRegime
    vol_multiplier: float
    correlation_surge: float
    liquidity_haircut: float
    transition_days: int


@dataclass(frozen=True)
class RegimeCrashResult:
    """Impact of a regime crash on the portfolio."""

    scenario_name: str
    portfolio_loss: float
    vol_adjusted_loss: float
    diversification_loss: float
    liquidity_cost: float
    total_impact: float
    survives: bool


REGIME_CRASH_SCENARIOS = (
    RegimeCrashScenario(
        name="Sudden Vol Spike",
        from_regime=RiskRegime.NORMAL,
        to_regime=RiskRegime.CRISIS,
        vol_multiplier=3.5,
        correlation_surge=0.30,
        liquidity_haircut=0.15,
        transition_days=3,
    ),
    RegimeCrashScenario(
        name="Correlation Collapse",
        from_regime=RiskRegime.NORMAL,
        to_regime=RiskRegime.STRESSED,
        vol_multiplier=2.0,
        correlation_surge=0.60,
        liquidity_haircut=0.10,
        transition_days=5,
    ),
    RegimeCrashScenario(
        name="Liquidity Evaporation",
        from_regime=RiskRegime.ELEVATED,
        to_regime=RiskRegime.CRISIS,
        vol_multiplier=2.5,
        correlation_surge=0.40,
        liquidity_haircut=0.40,
        transition_days=2,
    ),
    RegimeCrashScenario(
        name="Slow Grind to Crisis",
        from_regime=RiskRegime.NORMAL,
        to_regime=RiskRegime.STRESSED,
        vol_multiplier=1.5,
        correlation_surge=0.15,
        liquidity_haircut=0.05,
        transition_days=60,
    ),
)


class RegimeCrashEngine:
    """
    Simulates the impact of abrupt regime transitions.

    The key insight: in a regime crash, volatility, correlation, and
    liquidity all deteriorate simultaneously. The combined effect is
    worse than the sum of individual effects because:
    - Higher vol × higher correlation = portfolio vol explosion
    - Portfolio vol explosion + low liquidity = forced liquidation at worst prices
    """

    def __init__(
        self,
        scenarios: tuple[RegimeCrashScenario, ...] | None = None,
    ) -> None:
        self._scenarios = scenarios or REGIME_CRASH_SCENARIOS

    def run_all(
        self,
        portfolio_vol: float,
        gross_leverage: float,
        concentration_hhi: float,
        position_weights: dict[str, float],
    ) -> list[RegimeCrashResult]:
        return [
            self.run_scenario(
                scenario=s,
                portfolio_vol=portfolio_vol,
                gross_leverage=gross_leverage,
                concentration_hhi=concentration_hhi,
                position_weights=position_weights,
            )
            for s in self._scenarios
        ]

    def run_scenario(
        self,
        scenario: RegimeCrashScenario,
        portfolio_vol: float,
        gross_leverage: float,
        concentration_hhi: float,
        position_weights: dict[str, float],
    ) -> RegimeCrashResult:
        stressed_vol = portfolio_vol * scenario.vol_multiplier

        n_positions = len(position_weights)
        effective_n = 1.0 / max(concentration_hhi, 1e-6)
        div_benefit_normal = 1.0 / max(np.sqrt(effective_n), 1.0)
        div_benefit_stressed = 1.0 / max(
            np.sqrt(effective_n * (1.0 - scenario.correlation_surge)), 1.0
        )
        div_loss = max(0.0, div_benefit_stressed - div_benefit_normal)

        daily_stressed_vol = stressed_vol / np.sqrt(252)
        expected_loss = daily_stressed_vol * np.sqrt(scenario.transition_days) * gross_leverage
        expected_loss *= (1.0 + div_loss)

        liq_cost = scenario.liquidity_haircut * gross_leverage

        total = expected_loss + liq_cost

        return RegimeCrashResult(
            scenario_name=scenario.name,
            portfolio_loss=-expected_loss,
            vol_adjusted_loss=-expected_loss,
            diversification_loss=-div_loss * daily_stressed_vol * gross_leverage,
            liquidity_cost=-liq_cost,
            total_impact=-total,
            survives=total < 0.30,
        )
