"""
Backtest report — comprehensive summary of a completed backtest.

This is the deliverable. It must contain enough information for
a portfolio manager or risk officer to assess:
1. Is the alpha real?
2. What are the hidden risks?
3. What assumptions drive the result?
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backtesting.accounting.equity_curve import EquityCurveAnalysis
from backtesting.portfolio.pnl_engine import PnLEngine
from backtesting.portfolio.turnover_engine import TurnoverEngine

logger = logging.getLogger(__name__)

BACKTEST_WARNINGS = (
    "All backtest results are optimistic estimates of live performance.",
    "Historical alpha decays; past performance does not predict future results.",
    "Execution assumptions (slippage, spread, impact) critically affect returns.",
    "Transaction costs dominate high-turnover strategies.",
    "Multiple testing inflates apparent Sharpe ratios.",
    "Survivorship and look-ahead biases may be present in input data.",
)


@dataclass(frozen=True)
class BacktestReport:
    """Full backtest report."""

    strategy_name: str
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    initial_capital: float
    final_capital: float
    equity_analysis: EquityCurveAnalysis
    execution_summary: dict[str, float]
    cost_attribution: dict[str, float]
    turnover_annualized: float
    n_trades: int
    event_stats: dict[str, int]
    config_summary: dict[str, str]
    warnings: tuple[str, ...]
    additional_metrics: dict[str, float] = field(default_factory=dict)

    def summary_text(self) -> str:
        lines = [
            f"=== BACKTEST REPORT: {self.strategy_name} ===",
            f"Period: {self.start_date.date()} to {self.end_date.date()}",
            f"Initial capital: ${self.initial_capital:,.0f}",
            f"Final capital:   ${self.final_capital:,.0f}",
            "",
            "--- Performance ---",
            f"Total return:      {self.equity_analysis.total_return:.2%}",
            f"Annualized return: {self.equity_analysis.annualized_return:.2%}",
            f"Annualized vol:    {self.equity_analysis.annualized_volatility:.2%}",
            f"Sharpe ratio:      {self.equity_analysis.sharpe_ratio:.2f}",
            f"Sortino ratio:     {self.equity_analysis.sortino_ratio:.2f}",
            f"Calmar ratio:      {self.equity_analysis.calmar_ratio:.2f}",
            f"Max drawdown:      {self.equity_analysis.max_drawdown:.2%}",
            f"Max DD duration:   {self.equity_analysis.max_drawdown_duration_days} days",
            "",
            "--- Execution ---",
            f"Total trades:      {self.n_trades}",
            f"Annualized turnover: {self.turnover_annualized:.2f}x",
        ]

        if self.cost_attribution:
            lines.append("")
            lines.append("--- Cost Attribution ---")
            for k, v in self.cost_attribution.items():
                lines.append(f"  {k}: {v:.2%}")

        lines.append("")
        lines.append("--- Warnings ---")
        for w in self.warnings:
            lines.append(f"  * {w}")

        return "\n".join(lines)
