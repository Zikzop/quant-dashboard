"""
Tearsheet — unified backtest summary for institutional review.

Combines all report components into a single data structure
suitable for rendering in a dashboard or PDF.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

from backtesting.accounting.equity_curve import EquityCurveAnalysis, EquityCurveBuilder
from backtesting.reports.backtest_report import BacktestReport
from backtesting.reports.execution_diagnostics import ExecutionDiagnostics
from backtesting.reports.risk_report import RiskReport

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Tearsheet:
    """Institutional tearsheet combining all backtest analytics."""

    strategy_name: str
    backtest_report: BacktestReport
    risk_report: RiskReport
    execution_diagnostics: ExecutionDiagnostics
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    monthly_returns: pd.Series
    rolling_sharpe: pd.Series
    validation_summary: dict[str, Any]
    warnings: tuple[str, ...]


def generate_tearsheet(
    strategy_name: str,
    backtest_report: BacktestReport,
    risk_report: RiskReport,
    execution_diagnostics: ExecutionDiagnostics,
    equity_builder: EquityCurveBuilder,
    validation_summary: dict[str, Any] | None = None,
) -> Tearsheet:
    """Generate a complete institutional tearsheet."""
    eq = equity_builder.to_series()
    dd = equity_builder.drawdown_series()
    r = equity_builder.returns()

    monthly = r.resample("ME").apply(lambda x: (1 + x).prod() - 1) if len(r) > 0 else pd.Series(dtype=float)

    if len(r) > 63:
        rolling_sharpe = (
            r.rolling(63).mean() / r.rolling(63).std() * (252 ** 0.5)
        ).dropna()
    else:
        rolling_sharpe = pd.Series(dtype=float)

    all_warnings = list(backtest_report.warnings)
    all_warnings.extend(risk_report.warnings)

    return Tearsheet(
        strategy_name=strategy_name,
        backtest_report=backtest_report,
        risk_report=risk_report,
        execution_diagnostics=execution_diagnostics,
        equity_curve=eq,
        drawdown_curve=dd,
        monthly_returns=monthly,
        rolling_sharpe=rolling_sharpe,
        validation_summary=validation_summary or {},
        warnings=tuple(all_warnings),
    )
