"""
Risk orchestrator — the central coordinator of all risk engine components.

Aggregates exposure monitoring, volatility targeting, drawdown controls,
VaR/CVaR, stress testing, correlation analysis, and governance into a
single coherent risk assessment pipeline.

This is the top-level entry point for the risk engine. It:
1. Accepts portfolio state and market data
2. Runs all risk computations
3. Evaluates governance limits
4. Triggers escalations and actions
5. Produces a unified risk report
6. Maintains immutable audit trail

The orchestrator is portfolio-aware, regime-aware, and execution-aware.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from risk_engine.risk_config import RiskEngineConfig, RiskRegime

from risk_engine.exposure.exposure_monitor import ExposureMonitor, ExposureAssessment
from risk_engine.exposure.concentration_monitor import ConcentrationMonitor

from risk_engine.volatility.volatility_targeting import VolatilityTargetingEngine, VolTargetOutput
from risk_engine.volatility.realized_volatility import RealizedVolatilityEngine
from risk_engine.volatility.dynamic_scaling import DynamicScalingEngine

from risk_engine.drawdown.drawdown_monitor import DrawdownMonitor, DrawdownState
from risk_engine.drawdown.kill_switch import KillSwitch, KillSwitchAction
from risk_engine.drawdown.capital_preservation import CapitalPreservationEngine
from risk_engine.drawdown.recovery_monitor import RecoveryMonitor

from risk_engine.var.historical_var import HistoricalVaREngine
from risk_engine.var.parametric_var import ParametricVaREngine
from risk_engine.var.monte_carlo_var import MonteCarloVaREngine
from risk_engine.var.cvar_engine import CVaREngine
from risk_engine.var.tail_risk import TailRiskEngine

from risk_engine.stress_testing.historical_stress import HistoricalStressEngine
from risk_engine.stress_testing.hypothetical_stress import HypotheticalStressEngine
from risk_engine.stress_testing.liquidity_stress import LiquidityStressEngine
from risk_engine.stress_testing.regime_crash import RegimeCrashEngine
from risk_engine.stress_testing.correlation_breakdown import CorrelationBreakdownEngine

from risk_engine.correlation.rolling_correlation import RollingCorrelationEngine
from risk_engine.correlation.covariance_monitor import CovarianceMonitor
from risk_engine.correlation.correlation_regimes import CorrelationRegimeDetector
from risk_engine.correlation.diversification_decay import DiversificationDecayMonitor

from risk_engine.governance.breach_detection import BreachDetector, BreachReport
from risk_engine.governance.escalation_engine import EscalationEngine
from risk_engine.governance.risk_actions import RiskActionEngine, RiskActionOrder
from risk_engine.governance.audit_log import AuditLog, AuditEventType

from risk_engine.realtime.realtime_risk_monitor import RealtimeRiskMonitor, RiskSnapshot

from risk_engine.reports.portfolio_risk_report import PortfolioRiskReport
from risk_engine.reports.stress_report import StressTestReport

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RiskAssessment:
    """Complete risk assessment output from one orchestrator cycle."""

    timestamp: pd.Timestamp
    exposure: ExposureAssessment
    drawdown: DrawdownState
    kill_switch: KillSwitchAction
    vol_target: VolTargetOutput | None
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    mean_correlation: float
    risk_regime: RiskRegime
    breach_report: BreachReport
    actions: tuple[RiskActionOrder, ...]
    snapshot: RiskSnapshot
    warnings: tuple[str, ...]


class RiskOrchestrator:
    """
    Central risk engine coordinator.

    Usage:
        orchestrator = RiskOrchestrator(config)
        assessment = orchestrator.assess(
            positions=..., prices=..., nav=...,
            returns=..., timestamp=...,
        )
        print(orchestrator.generate_report().summary_text())
    """

    def __init__(self, config: RiskEngineConfig | None = None) -> None:
        self._config = config or RiskEngineConfig()

        self._exposure = ExposureMonitor(config=self._config.exposure)
        self._vol_engine = RealizedVolatilityEngine(
            lookback_days=self._config.volatility.vol_lookback_days,
            ewm_halflife=self._config.volatility.vol_halflife_days,
        )
        self._vol_target = VolatilityTargetingEngine(config=self._config.volatility)
        self._dynamic_scaling = DynamicScalingEngine()

        self._drawdown = DrawdownMonitor(config=self._config.drawdown)
        self._kill_switch = KillSwitch(config=self._config.drawdown)
        self._capital_pres = CapitalPreservationEngine(config=self._config.drawdown)
        self._recovery = RecoveryMonitor(config=self._config.drawdown)

        self._hist_var = HistoricalVaREngine(config=self._config.var)
        self._param_var = ParametricVaREngine(config=self._config.var)
        self._mc_var = MonteCarloVaREngine(config=self._config.var)
        self._cvar = CVaREngine(config=self._config.var)
        self._tail_risk = TailRiskEngine()

        self._hist_stress = HistoricalStressEngine()
        self._hypo_stress = HypotheticalStressEngine()
        self._liq_stress = LiquidityStressEngine()
        self._regime_crash = RegimeCrashEngine()
        self._corr_breakdown = CorrelationBreakdownEngine()

        self._rolling_corr = RollingCorrelationEngine(config=self._config.correlation)
        self._cov_monitor = CovarianceMonitor(config=self._config.correlation)
        self._corr_regime = CorrelationRegimeDetector(config=self._config.correlation)
        self._div_decay = DiversificationDecayMonitor()

        self._breach_detector = BreachDetector()
        self._escalation = EscalationEngine(
            cooldown_seconds=self._config.governance.escalation_cooldown_seconds,
        )
        self._action_engine = RiskActionEngine()
        self._audit_log = AuditLog()

        self._realtime = RealtimeRiskMonitor(config=self._config)

        self._last_assessment: RiskAssessment | None = None

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    @property
    def kill_switch(self) -> KillSwitch:
        return self._kill_switch

    @property
    def latest(self) -> RiskAssessment | None:
        return self._last_assessment

    def assess(
        self,
        positions: dict[str, float],
        prices: dict[str, float],
        nav: float,
        timestamp: pd.Timestamp,
        returns: pd.Series | None = None,
        multi_asset_returns: pd.DataFrame | None = None,
        volatilities: dict[str, float] | None = None,
        sector_map: dict[str, str] | None = None,
        avg_volumes: dict[str, float] | None = None,
        strategy_pnls: dict[str, float] | None = None,
    ) -> RiskAssessment:
        """
        Run complete risk assessment cycle.

        Parameters
        ----------
        positions : symbol -> signed quantity
        prices : symbol -> current price
        nav : portfolio net asset value
        timestamp : current time
        returns : portfolio-level daily returns (for VaR, vol)
        multi_asset_returns : per-asset returns DataFrame (for correlation)
        volatilities : per-asset annualized vols (for vol-adjusted exposure)
        sector_map : symbol -> sector (for concentration)
        avg_volumes : symbol -> average daily volume (for liquidity)
        strategy_pnls : strategy -> PnL (for kill-switch targeting)
        """
        warnings: list[str] = []

        exposure = self._exposure.assess(
            positions=positions,
            prices=prices,
            nav=nav,
            timestamp=timestamp,
            volatilities=volatilities,
            sector_map=sector_map,
        )

        dd_state = self._drawdown.update(timestamp=timestamp, portfolio_value=nav)

        ks_action = self._kill_switch.evaluate(
            current_drawdown=dd_state.current_drawdown,
            drawdown_speed=dd_state.drawdown_speed,
            timestamp=timestamp,
            strategy_pnls=strategy_pnls,
        )

        self._recovery.update(
            current_drawdown=dd_state.current_drawdown,
            timestamp=timestamp,
        )

        vol_target_out = None
        if returns is not None and len(returns) >= 20:
            vol_est = self._vol_engine.estimate_from_returns(returns)
            realized_vol = vol_est.annualized_composite
            vol_target_out = self._vol_target.compute(
                returns=returns,
                current_leverage=exposure.exposure.gross_leverage,
            )
        else:
            realized_vol = 0.0

        var_95 = 0.0
        var_99 = 0.0
        cvar_95 = 0.0
        cvar_99 = 0.0
        if returns is not None and len(returns) >= self._config.var.min_observations:
            hist_var = self._hist_var.compute(returns)
            var_95 = hist_var.var_levels.get(0.95, 0.0)
            var_99 = hist_var.var_levels.get(0.99, 0.0)

            cvar_result = self._cvar.compute(returns)
            cvar_95 = cvar_result.cvar_levels.get(0.95, 0.0)
            cvar_99 = cvar_result.cvar_levels.get(0.99, 0.0)

        mean_corr = 0.0
        if multi_asset_returns is not None and multi_asset_returns.shape[1] >= 2:
            corr_snap = self._rolling_corr.compute(
                returns=multi_asset_returns,
                timestamp=timestamp,
            )
            mean_corr = corr_snap.mean_pairwise_correlation

        overall_regime = self._determine_regime(
            exposure_regime=exposure.risk_regime,
            drawdown_regime=dd_state.risk_regime,
            mean_corr=mean_corr,
        )

        metrics = {
            "gross_leverage": exposure.exposure.gross_leverage,
            "net_leverage": abs(exposure.exposure.net_leverage),
            "max_single_name_weight": exposure.concentration.max_single_name,
            "hhi": exposure.concentration.hhi,
            "var_95": var_95,
            "var_99": var_99,
            "drawdown": dd_state.current_drawdown,
            "mean_correlation": mean_corr,
            "realized_vol_ratio": (
                realized_vol / self._config.volatility.target_volatility
                if self._config.volatility.target_volatility > 0 else 0.0
            ),
        }

        breach_report = self._breach_detector.evaluate(
            metrics=metrics,
            timestamp=timestamp,
        )

        escalations = self._escalation.process(breach_report)
        actions = self._action_engine.generate_actions(escalations)

        for status in breach_report.breached_limits:
            self._audit_log.record(
                event_type=AuditEventType.BREACH_DETECTED,
                severity=status.limit.escalation_level.value,
                source="orchestrator",
                message=f"{status.limit.name}: {status.current_value:.4f} vs {status.limit.threshold:.4f}",
                timestamp=timestamp,
                details={"metric": status.limit.metric, "value": status.current_value},
            )

        if ks_action.state.value != "ACTIVE":
            self._audit_log.record(
                event_type=AuditEventType.KILL_SWITCH_ACTIVATED
                if ks_action.state.value == "HALTED"
                else AuditEventType.RISK_STATE_SNAPSHOT,
                severity="EMERGENCY" if ks_action.state.value == "HALTED" else "WARNING",
                source="kill_switch",
                message=ks_action.rationale,
                timestamp=timestamp,
            )

        if exposure.breaches:
            warnings.extend(exposure.breaches)
        if dd_state.drawdown_stage != "NORMAL":
            warnings.append(f"Drawdown stage: {dd_state.drawdown_stage}")
        if overall_regime != RiskRegime.NORMAL:
            warnings.append(f"Risk regime: {overall_regime.value}")

        snapshot = self._realtime.update(
            timestamp=timestamp,
            nav=nav,
            gross_leverage=exposure.exposure.gross_leverage,
            net_leverage=exposure.exposure.net_leverage,
            drawdown=dd_state.current_drawdown,
            drawdown_stage=dd_state.drawdown_stage,
            kill_switch_state=ks_action.state.value,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            realized_vol=realized_vol,
            target_leverage=vol_target_out.final_leverage if vol_target_out else 1.0,
            mean_correlation=mean_corr,
            concentration_hhi=exposure.concentration.hhi,
            risk_regime=overall_regime,
            n_breaches=breach_report.n_breached,
            warnings=warnings,
        )

        assessment = RiskAssessment(
            timestamp=timestamp,
            exposure=exposure,
            drawdown=dd_state,
            kill_switch=ks_action,
            vol_target=vol_target_out,
            var_95=var_95,
            var_99=var_99,
            cvar_95=cvar_95,
            cvar_99=cvar_99,
            mean_correlation=mean_corr,
            risk_regime=overall_regime,
            breach_report=breach_report,
            actions=tuple(actions),
            snapshot=snapshot,
            warnings=tuple(warnings),
        )

        self._last_assessment = assessment
        return assessment

    def run_stress_tests(
        self,
        position_weights: dict[str, float],
        position_vols: dict[str, float] | None = None,
        position_betas: dict[str, float] | None = None,
        current_leverage: float = 1.0,
        portfolio_vol: float = 0.15,
        concentration_hhi: float = 0.10,
        positions: dict[str, float] | None = None,
        prices: dict[str, float] | None = None,
        avg_volumes: dict[str, float] | None = None,
        nav: float = 1_000_000.0,
    ) -> StressTestReport:
        """Run all stress tests and return consolidated report."""
        historical = self._hist_stress.run_all(
            position_weights=position_weights,
            position_betas=position_betas,
            current_leverage=current_leverage,
        )

        hypothetical = self._hypo_stress.run_all(
            position_weights=position_weights,
            current_leverage=current_leverage,
        )

        liq_result = None
        if positions and prices and avg_volumes:
            liq_result = self._liq_stress.assess(
                positions=positions,
                prices=prices,
                avg_volumes=avg_volumes,
                nav=nav,
            )

        regime_results = self._regime_crash.run_all(
            portfolio_vol=portfolio_vol,
            gross_leverage=current_leverage,
            concentration_hhi=concentration_hhi,
            position_weights=position_weights,
        )

        return StressTestReport(
            historical_results=historical,
            hypothetical_results=hypothetical,
            liquidity_result=liq_result,
            regime_crash_results=regime_results,
        )

    def generate_report(self) -> PortfolioRiskReport:
        """Generate comprehensive risk report from latest assessment."""
        if self._last_assessment is None:
            return PortfolioRiskReport(report_date=pd.Timestamp.now(tz="UTC"))

        a = self._last_assessment
        return PortfolioRiskReport(
            report_date=a.timestamp,
            nav=a.snapshot.nav,
            gross_leverage=a.exposure.exposure.gross_leverage,
            net_leverage=a.exposure.exposure.net_leverage,
            current_drawdown=a.drawdown.current_drawdown,
            max_drawdown=a.drawdown.max_drawdown_trailing,
            var_95=a.var_95,
            var_99=a.var_99,
            cvar_95=a.cvar_95,
            cvar_99=a.cvar_99,
            realized_vol=a.snapshot.realized_vol,
            target_vol=self._config.volatility.target_volatility,
            mean_correlation=a.mean_correlation,
            concentration_hhi=a.exposure.concentration.hhi,
            effective_n_assets=a.exposure.concentration.effective_n,
            n_positions=a.exposure.concentration.n_positions,
            n_breaches=a.breach_report.n_breached,
            risk_regime=a.risk_regime.value,
            kill_switch_state=a.kill_switch.state.value,
            risk_score=a.snapshot.portfolio_risk_score,
            warnings=list(a.warnings),
        )

    @staticmethod
    def _determine_regime(
        exposure_regime: RiskRegime,
        drawdown_regime: RiskRegime,
        mean_corr: float,
    ) -> RiskRegime:
        """Take the worst regime across all dimensions."""
        regimes = [exposure_regime, drawdown_regime]

        if mean_corr > 0.8:
            regimes.append(RiskRegime.CRISIS)
        elif mean_corr > 0.6:
            regimes.append(RiskRegime.STRESSED)
        elif mean_corr > 0.4:
            regimes.append(RiskRegime.ELEVATED)

        severity = {
            RiskRegime.NORMAL: 0,
            RiskRegime.ELEVATED: 1,
            RiskRegime.STRESSED: 2,
            RiskRegime.CRISIS: 3,
        }
        return max(regimes, key=lambda r: severity[r])
