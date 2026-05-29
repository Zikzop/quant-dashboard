"""
Hypothetical stress scenarios — adversarial "what-if" testing.

Unlike historical scenarios, hypothetical tests don't rely on past crises.
They test the portfolio against plausible-but-unseen events: interest rate
shocks, inflation spikes, sector rotation, geopolitical disruption.

The goal is to find portfolio fragilities before markets find them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HypotheticalScenario:
    """User-defined or systematic hypothetical scenario."""

    name: str
    description: str
    asset_shocks: dict[str, float]
    vol_multiplier: float = 2.0
    correlation_override: float | None = None


@dataclass(frozen=True)
class HypotheticalResult:
    """Result of a hypothetical stress test."""

    scenario_name: str
    portfolio_loss: float
    position_losses: dict[str, float]
    worst_position: str
    worst_loss: float
    survives: bool


STANDARD_HYPOTHETICALS = (
    HypotheticalScenario(
        name="Rate Shock +200bps",
        description="Rapid 200bp rate increase; duration-sensitive assets fall",
        asset_shocks={"_default": -0.05, "_bonds": -0.15, "_growth": -0.12},
    ),
    HypotheticalScenario(
        name="Inflation Spike",
        description="Unexpected 3% inflation increase; real assets outperform",
        asset_shocks={"_default": -0.08, "_commodities": 0.10, "_tips": 0.02},
    ),
    HypotheticalScenario(
        name="Liquidity Freeze",
        description="Credit spreads widen 300bps; small-cap/HY crash",
        asset_shocks={"_default": -0.15, "_small_cap": -0.25, "_hy_credit": -0.20},
        vol_multiplier=3.0,
    ),
    HypotheticalScenario(
        name="Sector Rotation",
        description="Growth-to-value rotation; momentum reversal",
        asset_shocks={"_default": -0.02, "_growth": -0.15, "_value": 0.08},
    ),
    HypotheticalScenario(
        name="Geopolitical Shock",
        description="Major geopolitical event; flight to quality",
        asset_shocks={"_default": -0.12, "_em": -0.25, "_gold": 0.08},
        vol_multiplier=3.5,
        correlation_override=0.80,
    ),
)


class HypotheticalStressEngine:
    """
    Applies hypothetical stress scenarios to portfolio.

    Each scenario specifies per-asset or per-category shocks. Assets
    not explicitly shocked receive the _default shock level.
    """

    def __init__(
        self,
        scenarios: tuple[HypotheticalScenario, ...] | None = None,
    ) -> None:
        self._scenarios = scenarios or STANDARD_HYPOTHETICALS

    def run_all(
        self,
        position_weights: dict[str, float],
        asset_categories: dict[str, str] | None = None,
        current_leverage: float = 1.0,
    ) -> list[HypotheticalResult]:
        results = []
        for scenario in self._scenarios:
            result = self.run_scenario(
                scenario=scenario,
                position_weights=position_weights,
                asset_categories=asset_categories,
                current_leverage=current_leverage,
            )
            results.append(result)
        return results

    def run_scenario(
        self,
        scenario: HypotheticalScenario,
        position_weights: dict[str, float],
        asset_categories: dict[str, str] | None = None,
        current_leverage: float = 1.0,
    ) -> HypotheticalResult:
        if not position_weights:
            return HypotheticalResult(
                scenario_name=scenario.name,
                portfolio_loss=0.0,
                position_losses={},
                worst_position="N/A",
                worst_loss=0.0,
                survives=True,
            )

        categories = asset_categories or {}
        default_shock = scenario.asset_shocks.get("_default", -0.10)

        position_losses: dict[str, float] = {}
        for symbol, weight in position_weights.items():
            cat = categories.get(symbol, "")
            cat_key = f"_{cat}" if cat else ""
            shock = scenario.asset_shocks.get(cat_key, default_shock)
            position_losses[symbol] = weight * shock

        portfolio_loss = sum(position_losses.values()) * current_leverage

        worst_sym = min(position_losses, key=position_losses.get) if position_losses else "N/A"
        worst_loss = position_losses.get(worst_sym, 0.0)

        return HypotheticalResult(
            scenario_name=scenario.name,
            portfolio_loss=portfolio_loss,
            position_losses=position_losses,
            worst_position=worst_sym,
            worst_loss=worst_loss,
            survives=portfolio_loss > -0.30,
        )
