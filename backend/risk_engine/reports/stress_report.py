"""
Stress test report — consolidated results from all stress testing engines.

Presents historical, hypothetical, liquidity, and regime crash results
in a unified format for risk committee review.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from risk_engine.stress_testing.historical_stress import StressResult
from risk_engine.stress_testing.hypothetical_stress import HypotheticalResult
from risk_engine.stress_testing.liquidity_stress import LiquidityStressResult
from risk_engine.stress_testing.regime_crash import RegimeCrashResult

logger = logging.getLogger(__name__)


@dataclass
class StressTestReport:
    """Consolidated stress test report."""

    historical_results: list[StressResult] = field(default_factory=list)
    hypothetical_results: list[HypotheticalResult] = field(default_factory=list)
    liquidity_result: LiquidityStressResult | None = None
    regime_crash_results: list[RegimeCrashResult] = field(default_factory=list)

    @property
    def worst_historical(self) -> StressResult | None:
        if not self.historical_results:
            return None
        return min(self.historical_results, key=lambda r: r.portfolio_loss)

    @property
    def worst_hypothetical(self) -> HypotheticalResult | None:
        if not self.hypothetical_results:
            return None
        return min(self.hypothetical_results, key=lambda r: r.portfolio_loss)

    @property
    def worst_overall_loss(self) -> float:
        losses = []
        if self.historical_results:
            losses.extend(r.portfolio_loss for r in self.historical_results)
        if self.hypothetical_results:
            losses.extend(r.portfolio_loss for r in self.hypothetical_results)
        if self.regime_crash_results:
            losses.extend(r.total_impact for r in self.regime_crash_results)
        return min(losses) if losses else 0.0

    @property
    def any_survival_failure(self) -> bool:
        for r in self.hypothetical_results:
            if not r.survives:
                return True
        for r in self.regime_crash_results:
            if not r.survives:
                return True
        return False

    def summary_text(self) -> str:
        lines = ["=== STRESS TEST REPORT ===", ""]

        if self.historical_results:
            lines.append("--- HISTORICAL SCENARIOS ---")
            for r in sorted(self.historical_results, key=lambda x: x.portfolio_loss):
                flag = " ⚠" if r.portfolio_loss < -0.20 else ""
                lines.append(
                    f"  {r.scenario_name:40s} Loss: {r.portfolio_loss:+.2%}{flag}"
                )
            lines.append("")

        if self.hypothetical_results:
            lines.append("--- HYPOTHETICAL SCENARIOS ---")
            for r in sorted(self.hypothetical_results, key=lambda x: x.portfolio_loss):
                status = "SURVIVES" if r.survives else "FAILS"
                lines.append(
                    f"  {r.scenario_name:40s} Loss: {r.portfolio_loss:+.2%}  [{status}]"
                )
            lines.append("")

        if self.liquidity_result:
            lr = self.liquidity_result
            lines.append("--- LIQUIDITY STRESS ---")
            lines.append(f"  Normal liquidation cost:  {lr.total_liquidation_cost:.2%}")
            lines.append(f"  Stress liquidation cost:  {lr.stress_liquidation_cost:.2%}")
            lines.append(f"  Days to liquidate:        {lr.weighted_days_to_liquidate:.1f}")
            lines.append(f"  Illiquid weight:          {lr.illiquid_weight:.2%}")
            lines.append("")

        if self.regime_crash_results:
            lines.append("--- REGIME CRASH SCENARIOS ---")
            for r in sorted(self.regime_crash_results, key=lambda x: x.total_impact):
                status = "SURVIVES" if r.survives else "FAILS"
                lines.append(
                    f"  {r.scenario_name:40s} Impact: {r.total_impact:+.2%}  [{status}]"
                )
            lines.append("")

        worst = self.worst_overall_loss
        lines.append(f"WORST OVERALL LOSS: {worst:+.2%}")
        if self.any_survival_failure:
            lines.append("⚠ PORTFOLIO FAILS ONE OR MORE SURVIVAL TESTS")

        return "\n".join(lines)
