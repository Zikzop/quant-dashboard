"""
Simulation configuration — all assumptions explicit, nothing hidden.

Every parameter that affects backtest realism must live here.
No magic numbers buried in execution or portfolio code.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExecutionConfig:
    """Execution simulation parameters."""

    base_slippage_bps: float = 5.0
    volatility_slippage_multiplier: float = 1.5
    base_spread_bps: float = 3.0
    min_spread_bps: float = 1.0
    latency_mean_ms: float = 50.0
    latency_std_ms: float = 20.0
    market_impact_coefficient: float = 0.1
    market_impact_exponent: float = 0.5
    partial_fill_probability: float = 0.05
    min_fill_ratio: float = 0.5
    fill_probability: float = 0.98


@dataclass(frozen=True)
class PortfolioConfig:
    """Portfolio construction constraints."""

    initial_capital: float = 1_000_000.0
    max_gross_leverage: float = 1.0
    max_net_exposure: float = 1.0
    max_position_weight: float = 0.20
    target_volatility: float | None = 0.15
    max_turnover_daily: float = 0.50
    min_trade_size: float = 100.0
    rebalance_threshold: float = 0.02


@dataclass(frozen=True)
class CostConfig:
    """Transaction cost model parameters."""

    commission_per_share: float = 0.005
    commission_min_per_order: float = 1.0
    commission_max_pct: float = 0.005
    sec_fee_per_dollar: float = 0.0000278
    finra_taf_per_share: float = 0.000166
    exchange_fee_per_share: float = 0.003
    borrow_cost_annual_bps: float = 50.0


@dataclass(frozen=True)
class SimulationConfig:
    """
    Master simulation configuration.

    All assumptions are explicit. Changing any parameter here changes the
    realism of the backtest. Document every override.

    WARNING: Default parameters are already more realistic than most retail
    backtests, but they are still optimistic for illiquid instruments,
    large orders, or stressed markets.
    """

    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    costs: CostConfig = field(default_factory=CostConfig)
    random_seed: int | None = 42
    trading_days_per_year: int = 252

    @staticmethod
    def conservative() -> SimulationConfig:
        """Pessimistic configuration for stress-testing alpha robustness."""
        return SimulationConfig(
            execution=ExecutionConfig(
                base_slippage_bps=10.0,
                volatility_slippage_multiplier=2.5,
                base_spread_bps=8.0,
                market_impact_coefficient=0.2,
                partial_fill_probability=0.15,
                fill_probability=0.90,
            ),
            portfolio=PortfolioConfig(
                max_gross_leverage=0.8,
                max_position_weight=0.10,
                target_volatility=0.10,
            ),
            costs=CostConfig(
                commission_per_share=0.01,
                borrow_cost_annual_bps=100.0,
            ),
        )
