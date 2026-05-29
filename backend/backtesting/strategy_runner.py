"""
Strategy runner — high-level interface for running backtests with alpha registry integration.

This is the entry point for users who want to:
1. Select alphas from the registry
2. Configure simulation parameters
3. Run the backtest
4. Get comprehensive results with validation

It connects the alpha engine (Phase 4) to the backtesting engine (Phase 5).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from backtesting.backtest_engine import BacktestEngine
from backtesting.monte_carlo.block_bootstrap import BlockBootstrapConfig, run_block_bootstrap
from backtesting.reports.backtest_report import BacktestReport
from backtesting.reports.tearsheet import Tearsheet
from backtesting.simulation_config import SimulationConfig
from backtesting.validation.deflated_sharpe import compute_deflated_sharpe
from backtesting.validation.purged_walk_forward import PurgedWFConfig, run_purged_walk_forward

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrategySpec:
    """Specification for a backtest run."""

    name: str
    symbols: list[str]
    alpha_signals: dict[str, pd.DataFrame]
    market_data: dict[str, pd.DataFrame]
    config: SimulationConfig = field(default_factory=SimulationConfig)
    n_trials_tested: int = 1
    run_validation: bool = True
    run_bootstrap: bool = True


@dataclass(frozen=True)
class StrategyResult:
    """Complete strategy evaluation result."""

    backtest_report: BacktestReport
    tearsheet: Tearsheet | None
    validation: dict[str, Any]
    bootstrap: dict[str, Any]
    warnings: tuple[str, ...]


class StrategyRunner:
    """
    Runs a complete strategy evaluation pipeline.

    1. Backtest with execution realism
    2. Purged walk-forward OOS validation
    3. Block bootstrap confidence intervals
    4. Deflated Sharpe ratio test
    5. Comprehensive reporting
    """

    def run(self, spec: StrategySpec) -> StrategyResult:
        """Execute full strategy evaluation."""
        logger.info("Running strategy: %s", spec.name)

        engine = BacktestEngine(config=spec.config)
        report = engine.run(
            market_data=spec.market_data,
            alpha_signals=spec.alpha_signals,
        )

        tearsheet = engine.generate_tearsheet(strategy_name=spec.name)

        validation_results: dict[str, Any] = {}
        bootstrap_results: dict[str, Any] = {}
        all_warnings: list[str] = list(report.warnings)

        returns = engine.equity_builder.returns()

        if spec.run_validation and len(returns) > 200:
            validation_results = self._run_validation(
                returns, spec.n_trials_tested
            )
            if "warnings" in validation_results:
                all_warnings.extend(validation_results["warnings"])

        if spec.run_bootstrap and len(returns) > 100:
            bootstrap_results = self._run_bootstrap(returns)
            if "warnings" in bootstrap_results:
                all_warnings.extend(bootstrap_results["warnings"])

        return StrategyResult(
            backtest_report=report,
            tearsheet=tearsheet,
            validation=validation_results,
            bootstrap=bootstrap_results,
            warnings=tuple(all_warnings),
        )

    def _run_validation(
        self, returns: pd.Series, n_trials: int
    ) -> dict[str, Any]:
        """Run purged walk-forward + deflated Sharpe."""
        results: dict[str, Any] = {}
        warnings: list[str] = []

        try:
            wf = run_purged_walk_forward(returns)
            results["walk_forward"] = {
                "mean_oos_sharpe": wf.mean_oos_sharpe,
                "std_oos_sharpe": wf.std_oos_sharpe,
                "oos_vs_is_ratio": wf.oos_vs_is_ratio,
                "n_positive_folds": wf.n_positive_folds,
                "n_total_folds": wf.n_total_folds,
                "sharpe_decay_rate": wf.sharpe_decay_rate,
            }
            warnings.extend(wf.warnings)
        except ValueError as e:
            results["walk_forward"] = {"error": str(e)}

        if n_trials > 1:
            r = returns.values
            skew = float(pd.Series(r).skew())
            kurt = float(pd.Series(r).kurtosis() + 3)
            mu = np.mean(r)
            sigma = np.std(r, ddof=1)
            sharpe = mu / max(sigma, 1e-9) * np.sqrt(252)

            dsr = compute_deflated_sharpe(
                observed_sharpe=sharpe,
                n_observations=len(r),
                n_trials=n_trials,
                skewness=skew,
                kurtosis=kurt,
            )
            results["deflated_sharpe"] = {
                "observed": dsr.observed_sharpe,
                "deflated": dsr.deflated_sharpe,
                "expected_max": dsr.expected_max_sharpe,
                "p_value": dsr.p_value,
                "significant": dsr.is_significant,
            }
            warnings.extend(dsr.warnings)

        results["warnings"] = warnings
        return results

    def _run_bootstrap(self, returns: pd.Series) -> dict[str, Any]:
        """Run block bootstrap for confidence intervals."""
        warnings: list[str] = []
        try:
            boot = run_block_bootstrap(returns)
            result = {
                "mean_terminal": boot.mean_terminal,
                "ci_5_terminal": boot.ci_5,
                "ci_95_terminal": boot.ci_95,
                "prob_loss": boot.prob_loss,
                "mean_sharpe": boot.mean_sharpe,
                "sharpe_ci_5": boot.sharpe_ci_5,
                "sharpe_ci_95": boot.sharpe_ci_95,
                "mean_max_dd": boot.mean_max_dd,
                "worst_max_dd": boot.worst_max_dd,
            }
            if boot.prob_loss > 0.3:
                warnings.append(
                    f"Bootstrap: {boot.prob_loss:.0%} probability of loss — "
                    f"alpha is fragile"
                )
            if boot.sharpe_ci_5 < 0:
                warnings.append(
                    f"Bootstrap: 5th percentile Sharpe is negative "
                    f"({boot.sharpe_ci_5:.2f}) — alpha may not be real"
                )
            result["warnings"] = warnings
            return result
        except ValueError as e:
            return {"error": str(e), "warnings": warnings}
