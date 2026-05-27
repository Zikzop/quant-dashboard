"""
Portfolio risk report — comprehensive risk summary for institutional review.

This is the primary risk report consumed by portfolio managers and
risk committees. It aggregates all risk dimensions into a structured
narrative with quantitative detail.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRiskReport:
    """Comprehensive portfolio risk report."""

    report_date: pd.Timestamp
    nav: float = 0.0
    gross_leverage: float = 0.0
    net_leverage: float = 0.0
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    cvar_99: float = 0.0
    realized_vol: float = 0.0
    target_vol: float = 0.0
    mean_correlation: float = 0.0
    concentration_hhi: float = 0.0
    effective_n_assets: float = 0.0
    n_positions: int = 0
    n_breaches: int = 0
    risk_regime: str = "NORMAL"
    kill_switch_state: str = "ACTIVE"
    risk_score: float = 0.0
    stress_test_worst: float = 0.0
    stress_test_worst_scenario: str = ""
    warnings: list[str] = field(default_factory=list)
    model_limitations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.model_limitations = [
            "VaR underestimates tail risk — financial returns have fatter tails than any parametric model assumes",
            "Correlations are non-stationary — diversification benefits can evaporate during crises",
            "Stress scenarios are incomplete — the next crisis will differ from all historical precedents",
            "Volatility clustering means periods of calm do not predict continued calm",
            "Liquidity risk is not fully captured — exit costs can spike nonlinearly in stress",
            "Model risk: all risk measures are approximations based on assumed distributions",
        ]

    def summary_text(self) -> str:
        lines = [
            f"=== PORTFOLIO RISK REPORT — {self.report_date.strftime('%Y-%m-%d')} ===",
            "",
            f"NAV:                   ${self.nav:,.0f}",
            f"Risk Regime:           {self.risk_regime}",
            f"Kill Switch:           {self.kill_switch_state}",
            f"Composite Risk Score:  {self.risk_score:.1f}/100",
            "",
            "--- EXPOSURE ---",
            f"Gross Leverage:        {self.gross_leverage:.2f}x",
            f"Net Leverage:          {self.net_leverage:+.2f}x",
            f"Positions:             {self.n_positions}",
            f"Effective N:           {self.effective_n_assets:.1f}",
            f"HHI Concentration:     {self.concentration_hhi:.3f}",
            "",
            "--- RISK METRICS ---",
            f"Drawdown (current):    {self.current_drawdown:.2%}",
            f"Drawdown (max):        {self.max_drawdown:.2%}",
            f"Realized Vol (ann.):   {self.realized_vol:.2%}",
            f"Target Vol:            {self.target_vol:.2%}",
            f"VaR (95%):             {self.var_95:.2%}",
            f"VaR (99%):             {self.var_99:.2%}",
            f"CVaR (95%):            {self.cvar_95:.2%}",
            f"CVaR (99%):            {self.cvar_99:.2%}",
            "",
            "--- CORRELATION ---",
            f"Mean Pairwise:         {self.mean_correlation:.3f}",
            "",
            "--- STRESS TESTING ---",
            f"Worst Scenario:        {self.stress_test_worst_scenario}",
            f"Worst Loss:            {self.stress_test_worst:.2%}",
            "",
            "--- GOVERNANCE ---",
            f"Active Breaches:       {self.n_breaches}",
        ]

        if self.warnings:
            lines.append("")
            lines.append("--- WARNINGS ---")
            for w in self.warnings:
                lines.append(f"  • {w}")

        lines.append("")
        lines.append("--- MODEL LIMITATIONS ---")
        for lim in self.model_limitations:
            lines.append(f"  ⚠ {lim}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_date": self.report_date.isoformat(),
            "nav": self.nav,
            "gross_leverage": self.gross_leverage,
            "net_leverage": self.net_leverage,
            "drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown,
            "var_95": self.var_95,
            "var_99": self.var_99,
            "cvar_95": self.cvar_95,
            "cvar_99": self.cvar_99,
            "realized_vol": self.realized_vol,
            "mean_correlation": self.mean_correlation,
            "hhi": self.concentration_hhi,
            "n_positions": self.n_positions,
            "risk_regime": self.risk_regime,
            "risk_score": self.risk_score,
            "n_breaches": self.n_breaches,
            "warnings": self.warnings,
        }
