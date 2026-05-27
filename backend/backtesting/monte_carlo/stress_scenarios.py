"""
Stress scenarios — deterministic and stochastic adversarial testing.

Historical stress tests replay known crises. Hypothetical stress tests
construct plausible worst-case scenarios. Both are necessary because
the next crisis won't look exactly like the last one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StressScenario:
    """Definition of a single stress scenario."""

    name: str
    description: str
    daily_shocks: tuple[float, ...]
    volatility_multiplier: float = 1.0
    correlation_override: float | None = None


HISTORICAL_SCENARIOS: tuple[StressScenario, ...] = (
    StressScenario(
        name="black_monday_1987",
        description="Oct 19, 1987 — single-day 22% crash",
        daily_shocks=(-0.22,),
        volatility_multiplier=4.0,
    ),
    StressScenario(
        name="gfc_2008",
        description="Sep-Oct 2008 — sustained crisis over 30 days",
        daily_shocks=tuple(
            np.concatenate([
                np.random.default_rng(2008).normal(-0.02, 0.03, 30),
            ])
        ),
        volatility_multiplier=3.0,
    ),
    StressScenario(
        name="covid_crash_2020",
        description="Feb-Mar 2020 — rapid 34% drawdown",
        daily_shocks=tuple(
            np.concatenate([
                np.random.default_rng(2020).normal(-0.025, 0.04, 23),
            ])
        ),
        volatility_multiplier=5.0,
    ),
    StressScenario(
        name="flash_crash",
        description="Intraday-style extreme move and recovery",
        daily_shocks=(-0.08, 0.05, -0.03),
        volatility_multiplier=3.0,
    ),
    StressScenario(
        name="slow_bleed",
        description="Gradual sustained decline — death by 1000 cuts",
        daily_shocks=tuple([-0.005] * 60),
        volatility_multiplier=1.5,
    ),
)


@dataclass(frozen=True)
class StressTestResult:
    """Result of applying a stress scenario to a portfolio."""

    scenario_name: str
    initial_value: float
    final_value: float
    max_drawdown: float
    total_return: float
    worst_day: float
    recovery_needed: float
    equity_path: np.ndarray


def apply_stress_scenario(
    portfolio_value: float,
    scenario: StressScenario,
    current_positions_beta: float = 1.0,
) -> StressTestResult:
    """
    Apply a stress scenario to current portfolio value.

    current_positions_beta scales the shock by portfolio sensitivity
    to the market factor.
    """
    shocks = np.array(scenario.daily_shocks) * current_positions_beta
    equity = np.ones(len(shocks) + 1) * portfolio_value

    for i, shock in enumerate(shocks):
        equity[i + 1] = equity[i] * (1 + shock)

    running_max = np.maximum.accumulate(equity)
    drawdowns = (equity - running_max) / np.maximum(running_max, 1e-9)
    max_dd = float(np.min(drawdowns))
    total_ret = (equity[-1] / equity[0]) - 1
    recovery_needed = (equity[0] / max(equity[-1], 1e-9)) - 1

    return StressTestResult(
        scenario_name=scenario.name,
        initial_value=portfolio_value,
        final_value=float(equity[-1]),
        max_drawdown=max_dd,
        total_return=total_ret,
        worst_day=float(np.min(shocks)),
        recovery_needed=recovery_needed,
        equity_path=equity,
    )


def run_stress_battery(
    portfolio_value: float,
    scenarios: tuple[StressScenario, ...] | None = None,
    beta: float = 1.0,
) -> list[StressTestResult]:
    """Run all stress scenarios and return results."""
    scenarios = scenarios or HISTORICAL_SCENARIOS
    results = []
    for scenario in scenarios:
        result = apply_stress_scenario(portfolio_value, scenario, beta)
        results.append(result)
        logger.info(
            "Stress [%s]: drawdown=%.1f%%, return=%.1f%%",
            scenario.name,
            result.max_drawdown * 100,
            result.total_return * 100,
        )
    return results
