"""
Portfolio engine tests — validates core portfolio construction pipeline.

Tests cover:
- Base types and constraint validation
- Position sizing (volatility targeting, Kelly, risk budgeting)
- Optimization (covariance estimation, MVO, MinVar, risk parity, HRP)
- Allocation (exposure, regime)
- Rebalancing (engine, turnover control, transaction-aware)
- Portfolio analytics (diversification, concentration)
- Orchestrator end-to-end
"""

import numpy as np
import pandas as pd
import pytest


def _make_returns(n_assets: int = 5, n_obs: int = 252, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic return matrix for testing."""
    rng = np.random.default_rng(seed)
    symbols = [f"ASSET_{i}" for i in range(n_assets)]
    dates = pd.bdate_range("2023-01-01", periods=n_obs)
    data = rng.normal(0.0003, 0.015, (n_obs, n_assets))
    return pd.DataFrame(data, index=dates, columns=symbols)


def _make_covariance(returns: pd.DataFrame) -> pd.DataFrame:
    return returns.cov() * 252


class TestPortfolioBase:
    def test_portfolio_weights_validation(self):
        from portfolio_engine.portfolio_base import PortfolioWeights

        ts = pd.Timestamp("2024-01-01", tz="UTC")
        pw = PortfolioWeights(
            weights={"A": 0.5, "B": 0.3, "C": 0.2},
            timestamp=ts,
        )
        assert abs(pw.gross_leverage - 1.0) < 1e-8
        assert abs(pw.net_exposure - 1.0) < 1e-8
        assert pw.n_positions == 3

    def test_portfolio_weights_rejects_nan(self):
        from portfolio_engine.portfolio_base import PortfolioWeights

        with pytest.raises(ValueError, match="not finite"):
            PortfolioWeights(
                weights={"A": float("nan")},
                timestamp=pd.Timestamp.now(tz="UTC"),
            )

    def test_portfolio_constraints(self):
        from portfolio_engine.portfolio_base import PortfolioConstraints

        c = PortfolioConstraints(max_weight=0.25, long_only=True)
        assert c.max_weight == 0.25
        assert c.long_only is True

    def test_constraints_rejects_invalid(self):
        from portfolio_engine.portfolio_base import PortfolioConstraints

        with pytest.raises(ValueError):
            PortfolioConstraints(max_weight=-0.1)

    def test_validate_weights_against_constraints(self):
        from portfolio_engine.portfolio_base import (
            PortfolioWeights,
            PortfolioConstraints,
            validate_weights_against_constraints,
        )

        ts = pd.Timestamp.now(tz="UTC")
        w = PortfolioWeights(weights={"A": 0.6, "B": 0.4}, timestamp=ts)
        c = PortfolioConstraints(max_weight=0.5)
        violations = validate_weights_against_constraints(w, c)
        assert any("A" in v for v in violations)

    def test_compute_turnover(self):
        from portfolio_engine.portfolio_base import compute_turnover

        current = {"A": 0.5, "B": 0.5}
        target = {"A": 0.3, "B": 0.7}
        turnover, deltas = compute_turnover(current, target)
        assert abs(turnover - 0.2) < 1e-8
        assert abs(deltas["A"] - (-0.2)) < 1e-8

    def test_normalized_weights(self):
        from portfolio_engine.portfolio_base import PortfolioWeights

        ts = pd.Timestamp.now(tz="UTC")
        pw = PortfolioWeights(weights={"A": 0.6, "B": 0.4}, timestamp=ts)
        norm = pw.normalized(target_leverage=0.5)
        assert abs(norm.gross_leverage - 0.5) < 1e-6


class TestPositionSizing:
    def test_volatility_targeting(self):
        from portfolio_engine.position_sizing.volatility_targeting import (
            VolatilityTargetSizer,
            VolTargetConfig,
        )

        returns = _make_returns(1, 252).iloc[:, 0]
        sizer = VolatilityTargetSizer(VolTargetConfig(target_volatility=0.10))
        result = sizer.compute_leverage(returns)
        assert result.final_leverage > 0
        assert result.final_leverage <= 2.0
        assert result.realized_vol > 0

    def test_vol_target_insufficient_data(self):
        from portfolio_engine.position_sizing.volatility_targeting import (
            VolatilityTargetSizer,
            VolTargetConfig,
        )

        returns = pd.Series([0.01, 0.02])
        sizer = VolatilityTargetSizer(VolTargetConfig(min_observations=20))
        result = sizer.compute_leverage(returns)
        assert len(result.warnings) > 0

    def test_inverse_volatility_weights(self):
        from portfolio_engine.position_sizing.volatility_targeting import (
            inverse_volatility_weights,
        )

        vols = {"A": 0.10, "B": 0.20, "C": 0.30}
        weights = inverse_volatility_weights(vols)
        assert abs(sum(weights.values()) - 1.0) < 1e-8
        assert weights["A"] > weights["B"] > weights["C"]

    def test_kelly_sizing(self):
        from portfolio_engine.position_sizing.kelly_sizing import KellySizer, KellyConfig

        returns = _make_returns(3, 252)
        mu = returns.mean() * 252
        cov = returns.cov() * 252

        sizer = KellySizer(KellyConfig(fraction=0.25, max_leverage=1.5))
        result = sizer.compute(mu, cov)
        assert result.final_leverage <= 1.5
        assert result.kelly_fraction == 0.25

    def test_kelly_singular_matrix(self):
        from portfolio_engine.position_sizing.kelly_sizing import KellySizer

        mu = pd.Series({"A": 0.05, "B": 0.05})
        cov = pd.DataFrame(
            [[0.04, 0.04], [0.04, 0.04]],
            index=["A", "B"],
            columns=["A", "B"],
        )
        sizer = KellySizer()
        result = sizer.compute(mu, cov)
        assert len(result.warnings) > 0

    def test_risk_budgeting(self):
        from portfolio_engine.position_sizing.risk_budgeting import RiskBudgetSizer

        returns = _make_returns(4, 252)
        cov = _make_covariance(returns)

        sizer = RiskBudgetSizer()
        result = sizer.compute(cov)
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
        assert result.portfolio_vol > 0

    def test_dynamic_scaling(self):
        from portfolio_engine.position_sizing.dynamic_scaling import DynamicScaler

        scaler = DynamicScaler()
        result = scaler.compute_scale(
            current_drawdown=-0.10,
            regime="crisis",
            realized_vol=0.30,
            target_vol=0.15,
        )
        assert result.final_scale < 1.0
        assert result.drawdown_scale < 1.0
        assert result.regime_scale < 1.0


class TestOptimization:
    def test_covariance_estimation_ledoit_wolf(self):
        from portfolio_engine.optimization.covariance_estimation import (
            CovarianceEstimator,
            CovarianceConfig,
            CovarianceMethod,
        )

        returns = _make_returns(5, 252)
        estimator = CovarianceEstimator(
            CovarianceConfig(method=CovarianceMethod.LEDOIT_WOLF)
        )
        result = estimator.estimate(returns)
        assert result.covariance.shape == (5, 5)
        assert result.shrinkage_intensity > 0
        eigenvalues = np.linalg.eigvalsh(result.covariance.values)
        assert eigenvalues[0] > 0

    def test_covariance_ewm(self):
        from portfolio_engine.optimization.covariance_estimation import (
            CovarianceEstimator,
            CovarianceConfig,
            CovarianceMethod,
        )

        returns = _make_returns(3, 100)
        estimator = CovarianceEstimator(
            CovarianceConfig(method=CovarianceMethod.EWM, ewm_halflife=20)
        )
        result = estimator.estimate(returns)
        assert result.covariance.shape == (3, 3)

    def test_mean_variance_optimization(self):
        from portfolio_engine.optimization.mean_variance import MeanVarianceOptimizer
        from portfolio_engine.portfolio_base import PortfolioConstraints

        returns = _make_returns(4, 252)
        mu = returns.mean() * 252
        cov = _make_covariance(returns)

        opt = MeanVarianceOptimizer(
            constraints=PortfolioConstraints(long_only=True, max_weight=0.40)
        )
        result = opt.optimize(mu, cov)
        w = result.weights
        assert abs(sum(w.weights.values()) - 1.0) < 0.01
        assert all(v >= -1e-6 for v in w.weights.values())

    def test_minimum_variance(self):
        from portfolio_engine.optimization.minimum_variance import MinimumVarianceOptimizer
        from portfolio_engine.portfolio_base import PortfolioConstraints

        returns = _make_returns(5, 252)
        cov = _make_covariance(returns)

        opt = MinimumVarianceOptimizer(
            constraints=PortfolioConstraints(long_only=True)
        )
        result = opt.optimize(cov)
        assert result.portfolio_volatility > 0
        assert abs(sum(result.weights.weights.values()) - 1.0) < 0.01

    def test_risk_parity(self):
        from portfolio_engine.optimization.risk_parity import RiskParityOptimizer

        returns = _make_returns(4, 252)
        cov = _make_covariance(returns)

        opt = RiskParityOptimizer()
        result = opt.optimize(cov)
        rc = list(result.risk_contributions.values())
        assert all(r > 0 for r in rc)
        assert abs(sum(rc) - 1.0) < 0.05

    def test_hierarchical_risk_parity(self):
        from portfolio_engine.optimization.hierarchical_risk_parity import (
            HierarchicalRiskParityOptimizer,
        )

        returns = _make_returns(6, 252)
        cov = _make_covariance(returns)

        opt = HierarchicalRiskParityOptimizer()
        result = opt.optimize(cov)
        assert abs(sum(result.weights.weights.values()) - 1.0) < 0.01
        assert len(result.cluster_order) == 6

    def test_constraint_checker(self):
        from portfolio_engine.optimization.optimizer_constraints import (
            check_constraints,
            ConstraintCheckResult,
        )
        from portfolio_engine.portfolio_base import PortfolioConstraints

        weights = np.array([0.6, 0.4])
        constraints = PortfolioConstraints(max_weight=0.5, long_only=True)
        result = check_constraints(
            weights, constraints, symbols=["A", "B"],
        )
        assert not result.satisfied


class TestAllocation:
    def test_exposure_allocator(self):
        from portfolio_engine.allocation.exposure_allocator import ExposureAllocator

        allocator = ExposureAllocator()
        result = allocator.allocate(
            {"A": 0.5, "B": 0.3, "C": 0.2},
            asset_volatilities={"A": 0.20, "B": 0.10, "C": 0.15},
        )
        assert result.gross_leverage <= 2.0
        assert len(result.adjusted_weights) == 3

    def test_regime_allocator_crisis(self):
        from portfolio_engine.allocation.regime_allocator import RegimeAllocator

        allocator = RegimeAllocator()
        result = allocator.allocate(
            {"A": 0.5, "B": 0.5},
            regime="crisis",
            regime_confidence=0.9,
        )
        assert sum(abs(w) for w in result.adjusted_weights.values()) < 1.0


class TestRebalancing:
    def test_rebalance_engine_threshold(self):
        from portfolio_engine.rebalancing.rebalance_engine import (
            RebalanceEngine,
            RebalanceConfig,
        )

        engine = RebalanceEngine(RebalanceConfig(drift_threshold=0.05))
        decision = engine.evaluate(
            current_weights={"A": 0.5, "B": 0.5},
            target_weights={"A": 0.4, "B": 0.6},
            timestamp=pd.Timestamp("2024-06-01", tz="UTC"),
        )
        assert decision.should_rebalance
        assert abs(decision.max_drift - 0.1) < 1e-8

    def test_rebalance_suppressed_small_drift(self):
        from portfolio_engine.rebalancing.rebalance_engine import (
            RebalanceEngine,
            RebalanceConfig,
        )

        engine = RebalanceEngine(RebalanceConfig(drift_threshold=0.05))
        engine._last_rebalance_date = pd.Timestamp("2024-06-01", tz="UTC")
        decision = engine.evaluate(
            current_weights={"A": 0.50, "B": 0.50},
            target_weights={"A": 0.49, "B": 0.51},
            timestamp=pd.Timestamp("2024-06-02", tz="UTC"),
        )
        assert not decision.should_rebalance

    def test_turnover_control(self):
        from portfolio_engine.rebalancing.turnover_control import TurnoverController

        controller = TurnoverController()
        result = controller.control(
            current_weights={"A": 0.5, "B": 0.5},
            target_weights={"A": 0.0, "B": 1.0},
        )
        assert result.controlled_turnover <= 0.25

    def test_transaction_aware_rebalancing(self):
        from portfolio_engine.rebalancing.transaction_aware_rebalancing import (
            TransactionAwareRebalancer,
        )

        rebalancer = TransactionAwareRebalancer()
        result = rebalancer.rebalance(
            current_weights={"A": 0.5, "B": 0.5},
            target_weights={"A": 0.4, "B": 0.6},
            asset_volatilities={"A": 0.15, "B": 0.20},
            asset_alphas={"A": 0.05, "B": 0.05},
        )
        assert len(result.no_trade_zones) == 2


class TestPortfolioAnalytics:
    def test_diversification(self):
        from portfolio_engine.portfolio_analytics.diversification_metrics import (
            DiversificationAnalyzer,
        )

        analyzer = DiversificationAnalyzer()
        report = analyzer.analyze(
            weights={"A": 0.25, "B": 0.25, "C": 0.25, "D": 0.25},
        )
        assert abs(report.effective_n - 4.0) < 0.01
        assert abs(report.entropy_ratio - 1.0) < 0.01

    def test_concentration(self):
        from portfolio_engine.portfolio_analytics.concentration_analysis import (
            ConcentrationAnalyzer,
        )

        analyzer = ConcentrationAnalyzer()
        report = analyzer.analyze(weights={"A": 0.8, "B": 0.2})
        assert report.concentration_regime in ("elevated", "critical")
        assert report.top_1_weight > 0.7


class TestOrchestrator:
    def test_orchestrator_end_to_end(self):
        from portfolio_engine.orchestration.portfolio_orchestrator import (
            PortfolioOrchestrator,
            OrchestratorConfig,
        )
        from portfolio_engine.portfolio_base import PortfolioState, PortfolioConstraints, Position

        returns = _make_returns(4, 252)
        symbols = list(returns.columns)

        positions = {
            s: Position(
                symbol=s, quantity=100, market_price=50.0,
                market_value=5000.0, weight=0.25,
            )
            for s in symbols
        }
        state = PortfolioState(
            positions=positions,
            cash=0.0,
            nav=20000.0,
            timestamp=pd.Timestamp("2024-06-01", tz="UTC"),
            current_weights={s: 0.25 for s in symbols},
            returns_history=returns,
        )

        config = OrchestratorConfig(
            optimizer="risk_parity",
            constraints=PortfolioConstraints(long_only=True),
            enable_rebalance_check=False,
        )
        orchestrator = PortfolioOrchestrator(config)
        result = orchestrator.construct(
            portfolio_state=state,
            returns_history=returns,
            timestamp=pd.Timestamp("2024-06-01", tz="UTC"),
        )

        assert result.target_weights.n_positions > 0
        assert result.method == "risk_parity"
