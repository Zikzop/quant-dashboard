"""
Portfolio construction orchestrator — coordinates the full pipeline.

Sequence:
1. Estimate covariance
2. Run optimizer (MVO / MinVar / RP / HRP)
3. Apply position sizing (vol target / Kelly / risk budget)
4. Apply regime-aware scaling
5. Apply exposure constraints
6. Evaluate rebalancing decision
7. Apply turnover controls
8. Compute analytics
9. Produce allocation result

This is the top-level entry point for portfolio construction.
All sub-components are injected for testability and composability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from portfolio_engine.portfolio_base import (
    AllocationResult,
    PortfolioConstraints,
    PortfolioState,
    PortfolioWeights,
    compute_turnover,
    validate_weights_against_constraints,
)
from portfolio_engine.optimization.covariance_estimation import (
    CovarianceConfig,
    CovarianceEstimator,
)
from portfolio_engine.optimization.mean_variance import MeanVarianceOptimizer, MVOConfig
from portfolio_engine.optimization.minimum_variance import MinimumVarianceOptimizer, MinVarConfig
from portfolio_engine.optimization.risk_parity import RiskParityOptimizer, RiskParityConfig
from portfolio_engine.optimization.hierarchical_risk_parity import (
    HierarchicalRiskParityOptimizer,
    HRPConfig,
)
from portfolio_engine.position_sizing.volatility_targeting import (
    VolatilityTargetSizer,
    VolTargetConfig,
)
from portfolio_engine.position_sizing.dynamic_scaling import DynamicScaler, DynamicScalingConfig
from portfolio_engine.allocation.exposure_allocator import ExposureAllocator, ExposureConfig
from portfolio_engine.allocation.regime_allocator import RegimeAllocator, MarketRegime
from portfolio_engine.rebalancing.rebalance_engine import RebalanceEngine, RebalanceConfig
from portfolio_engine.rebalancing.turnover_control import TurnoverController, TurnoverConfig
from portfolio_engine.portfolio_analytics.diversification_metrics import DiversificationAnalyzer
from portfolio_engine.portfolio_analytics.concentration_analysis import ConcentrationAnalyzer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrchestratorConfig:
    optimizer: str = "risk_parity"
    constraints: PortfolioConstraints = field(default_factory=PortfolioConstraints)
    covariance: CovarianceConfig = field(default_factory=CovarianceConfig)
    vol_target: VolTargetConfig = field(default_factory=VolTargetConfig)
    rebalance: RebalanceConfig = field(default_factory=RebalanceConfig)
    turnover: TurnoverConfig = field(default_factory=TurnoverConfig)
    exposure: ExposureConfig = field(default_factory=ExposureConfig)
    dynamic_scaling: DynamicScalingConfig = field(default_factory=DynamicScalingConfig)
    enable_vol_targeting: bool = True
    enable_regime_scaling: bool = True
    enable_rebalance_check: bool = True


class PortfolioOrchestrator:
    """
    Full portfolio construction pipeline orchestrator.

    Usage:
        orchestrator = PortfolioOrchestrator(config)
        result = orchestrator.construct(
            portfolio_state=state,
            expected_returns=mu,
            returns_history=returns,
            regime="normal",
        )
    """

    def __init__(self, config: OrchestratorConfig | None = None) -> None:
        self._config = config or OrchestratorConfig()
        cfg = self._config

        self._cov_estimator = CovarianceEstimator(cfg.covariance)
        self._vol_sizer = VolatilityTargetSizer(cfg.vol_target)
        self._dynamic_scaler = DynamicScaler(cfg.dynamic_scaling)
        self._exposure_allocator = ExposureAllocator(cfg.exposure)
        self._regime_allocator = RegimeAllocator()
        self._rebalance_engine = RebalanceEngine(cfg.rebalance)
        self._turnover_controller = TurnoverController(cfg.turnover)
        self._diversification = DiversificationAnalyzer()
        self._concentration = ConcentrationAnalyzer()

        self._optimizers = {
            "mean_variance": lambda: MeanVarianceOptimizer(
                config=MVOConfig(), constraints=cfg.constraints,
            ),
            "minimum_variance": lambda: MinimumVarianceOptimizer(
                config=MinVarConfig(), constraints=cfg.constraints,
            ),
            "risk_parity": lambda: RiskParityOptimizer(
                config=RiskParityConfig(), constraints=cfg.constraints,
            ),
            "hierarchical_risk_parity": lambda: HierarchicalRiskParityOptimizer(
                config=HRPConfig(), constraints=cfg.constraints,
            ),
        }

        self._last_result: AllocationResult | None = None

    def construct(
        self,
        portfolio_state: PortfolioState,
        returns_history: pd.DataFrame,
        expected_returns: pd.Series | None = None,
        regime: str = "normal",
        regime_confidence: float = 1.0,
        sector_map: dict[str, str] | None = None,
        asset_volatilities: dict[str, float] | None = None,
        timestamp: pd.Timestamp | None = None,
    ) -> AllocationResult:
        """
        Execute the full portfolio construction pipeline.

        Parameters
        ----------
        portfolio_state : current portfolio snapshot
        returns_history : per-asset daily returns (DatetimeIndex, asset columns)
        expected_returns : annualized expected excess returns per asset (for MVO)
        regime : current market regime classification
        regime_confidence : confidence in regime classification [0,1]
        sector_map : symbol -> sector mapping
        asset_volatilities : per-asset annualized volatilities
        timestamp : evaluation timestamp
        """
        cfg = self._config
        warnings: list[str] = []
        ts = timestamp or pd.Timestamp.now(tz="UTC")

        cov_result = self._cov_estimator.estimate(returns_history)
        warnings.extend(cov_result.warnings)

        optimizer_name = cfg.optimizer
        optimizer_factory = self._optimizers.get(optimizer_name)
        if optimizer_factory is None:
            warnings.append(f"Unknown optimizer '{optimizer_name}', falling back to risk_parity")
            optimizer_factory = self._optimizers["risk_parity"]
            optimizer_name = "risk_parity"

        optimizer = optimizer_factory()

        if optimizer_name == "mean_variance":
            if expected_returns is None:
                warnings.append("MVO requires expected_returns; falling back to minimum_variance")
                optimizer = self._optimizers["minimum_variance"]()
                optimizer_name = "minimum_variance"
                opt_result = optimizer.optimize(
                    covariance_matrix=cov_result.covariance, timestamp=ts,
                )
            else:
                opt_result = optimizer.optimize(
                    expected_returns=expected_returns,
                    covariance_matrix=cov_result.covariance,
                    current_weights=portfolio_state.current_weights,
                    timestamp=ts,
                )
        elif optimizer_name == "minimum_variance":
            opt_result = optimizer.optimize(
                covariance_matrix=cov_result.covariance, timestamp=ts,
            )
        elif optimizer_name in ("risk_parity", "hierarchical_risk_parity"):
            kwargs: dict[str, Any] = {"covariance_matrix": cov_result.covariance, "timestamp": ts}
            if optimizer_name == "hierarchical_risk_parity":
                kwargs["correlation_matrix"] = cov_result.correlation
            opt_result = optimizer.optimize(**kwargs)
        else:
            raise ValueError(f"Unhandled optimizer: {optimizer_name}")

        raw_weights = opt_result.weights.weights
        risk_contributions = getattr(opt_result, "risk_contributions", {})
        expected_risk = getattr(opt_result, "portfolio_volatility", 0.0)
        expected_return = getattr(opt_result, "expected_return", 0.0)
        warnings.extend(getattr(opt_result, "warnings", []))

        if cfg.enable_vol_targeting and portfolio_state.returns_history is not None:
            port_returns = portfolio_state.returns_history.mean(axis=1)
            if len(port_returns) > 20:
                raw_weights, vol_result = self._vol_sizer.scale_weights(
                    raw_weights, port_returns,
                    current_leverage=portfolio_state.gross_leverage,
                )
                warnings.extend(vol_result.warnings)

        if cfg.enable_regime_scaling:
            regime_result = self._regime_allocator.allocate(
                raw_weights, regime, regime_confidence,
            )
            raw_weights = regime_result.adjusted_weights
            warnings.extend(regime_result.warnings)

        exp_result = self._exposure_allocator.allocate(
            raw_weights,
            asset_volatilities=asset_volatilities,
            nav=portfolio_state.nav,
        )
        raw_weights = exp_result.adjusted_weights
        warnings.extend(exp_result.warnings)

        turnover, weight_deltas = compute_turnover(
            portfolio_state.current_weights, raw_weights,
        )

        if cfg.enable_rebalance_check:
            rebal_decision = self._rebalance_engine.evaluate(
                portfolio_state.current_weights, raw_weights, ts,
            )
            warnings.extend(rebal_decision.warnings)

            if not rebal_decision.should_rebalance:
                return AllocationResult(
                    target_weights=PortfolioWeights(
                        weights=portfolio_state.current_weights,
                        timestamp=ts,
                        method="no_rebalance",
                    ),
                    current_weights=portfolio_state.current_weights,
                    weight_deltas={s: 0.0 for s in portfolio_state.current_weights},
                    turnover=0.0,
                    expected_risk=expected_risk,
                    expected_return=expected_return,
                    risk_contributions=risk_contributions,
                    method=optimizer_name,
                    constraints_satisfied=True,
                    constraint_violations=[],
                    warnings=warnings + [f"Rebalance suppressed: {rebal_decision.trigger_reason}"],
                    metadata={"rebalance_decision": rebal_decision.trigger_reason},
                )

        tc_result = self._turnover_controller.control(
            portfolio_state.current_weights, raw_weights,
        )
        final_deltas = tc_result.controlled_deltas
        final_weights = {
            s: portfolio_state.current_weights.get(s, 0.0) + final_deltas.get(s, 0.0)
            for s in set(portfolio_state.current_weights) | set(raw_weights)
        }
        final_turnover = tc_result.controlled_turnover
        warnings.extend(tc_result.warnings)

        target = PortfolioWeights(
            weights=final_weights,
            timestamp=ts,
            method=optimizer_name,
        )

        violations = validate_weights_against_constraints(
            target, cfg.constraints, sector_map,
        )

        result = AllocationResult(
            target_weights=target,
            current_weights=portfolio_state.current_weights,
            weight_deltas=final_deltas,
            turnover=final_turnover,
            expected_risk=expected_risk,
            expected_return=expected_return,
            risk_contributions=risk_contributions,
            method=optimizer_name,
            constraints_satisfied=len([v for v in violations if "exceeds" in v.lower()]) == 0,
            constraint_violations=violations,
            warnings=warnings,
            metadata={
                "covariance_method": cov_result.method.value,
                "condition_number": cov_result.condition_number,
                "shrinkage": cov_result.shrinkage_intensity,
            },
        )
        self._last_result = result
        return result
