"""
Risk engine configuration — all thresholds, limits, and assumptions explicit.

Every parameter that governs risk behavior lives here.
No hidden thresholds buried in monitoring or governance code.

WARNING: These defaults are calibrated for a diversified equity portfolio.
Concentrated, leveraged, or illiquid strategies require tighter limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique


@unique
class RiskRegime(Enum):
    """Market risk regime classification."""
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    STRESSED = "STRESSED"
    CRISIS = "CRISIS"


@unique
class EscalationLevel(Enum):
    """Governance escalation severity."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass(frozen=True)
class ExposureConfig:
    """Exposure monitoring thresholds."""
    max_gross_leverage: float = 2.0
    max_net_exposure_ratio: float = 1.0
    max_single_name_weight: float = 0.15
    max_sector_weight: float = 0.30
    concentration_hhi_warning: float = 0.15
    concentration_hhi_critical: float = 0.25
    min_positions_for_diversification: int = 5
    volatility_adjusted_exposure: bool = True


@dataclass(frozen=True)
class VolatilityConfig:
    """Volatility targeting parameters."""
    target_volatility: float = 0.15
    vol_lookback_days: int = 60
    vol_halflife_days: int = 20
    min_leverage: float = 0.1
    max_leverage: float = 2.0
    scaling_dampening: float = 0.5
    rebalance_threshold: float = 0.10
    vol_floor: float = 0.05
    vol_ceiling: float = 0.60


@dataclass(frozen=True)
class DrawdownConfig:
    """Drawdown control thresholds — staged, not binary."""
    warning_threshold: float = -0.05
    reduce_threshold: float = -0.10
    critical_threshold: float = -0.15
    kill_switch_threshold: float = -0.20
    leverage_reduction_per_stage: float = 0.30
    recovery_buffer_pct: float = 0.02
    min_recovery_days: int = 5
    trailing_window_days: int = 252


@dataclass(frozen=True)
class VaRConfig:
    """VaR/CVaR calculation parameters."""
    confidence_levels: tuple[float, ...] = (0.95, 0.99)
    lookback_days: int = 504
    monte_carlo_simulations: int = 10_000
    mc_path_length: int = 10
    parametric_distribution: str = "student_t"
    min_observations: int = 60
    decay_factor: float = 0.94


@dataclass(frozen=True)
class StressTestConfig:
    """Stress testing parameters."""
    correlation_shock_multiplier: float = 1.5
    liquidity_haircut_pct: float = 0.30
    vol_expansion_factor: float = 2.5
    max_scenario_loss_tolerance: float = -0.30
    include_historical_scenarios: bool = True
    include_hypothetical_scenarios: bool = True


@dataclass(frozen=True)
class CorrelationConfig:
    """Correlation monitoring parameters."""
    rolling_window_days: int = 63
    long_window_days: int = 252
    regime_threshold: float = 0.3
    instability_z_threshold: float = 2.0
    min_history_days: int = 60
    ewm_halflife_days: int = 30


@dataclass(frozen=True)
class GovernanceConfig:
    """Risk governance parameters."""
    max_daily_var_pct: float = 0.02
    max_portfolio_var_pct: float = 0.05
    auto_reduce_on_breach: bool = True
    escalation_cooldown_seconds: int = 300
    audit_log_retention_days: int = 365
    require_acknowledgment_for_critical: bool = True


@dataclass(frozen=True)
class RiskEngineConfig:
    """
    Master risk engine configuration.

    All risk thresholds and assumptions are explicit.
    Override individual sub-configs for strategy-specific calibration.
    """
    exposure: ExposureConfig = field(default_factory=ExposureConfig)
    volatility: VolatilityConfig = field(default_factory=VolatilityConfig)
    drawdown: DrawdownConfig = field(default_factory=DrawdownConfig)
    var: VaRConfig = field(default_factory=VaRConfig)
    stress: StressTestConfig = field(default_factory=StressTestConfig)
    correlation: CorrelationConfig = field(default_factory=CorrelationConfig)
    governance: GovernanceConfig = field(default_factory=GovernanceConfig)
    trading_days_per_year: int = 252

    @staticmethod
    def conservative() -> RiskEngineConfig:
        """Tight limits for high-conviction, capital-preservation portfolios."""
        return RiskEngineConfig(
            exposure=ExposureConfig(
                max_gross_leverage=1.0,
                max_net_exposure_ratio=0.8,
                max_single_name_weight=0.10,
                concentration_hhi_warning=0.10,
            ),
            volatility=VolatilityConfig(
                target_volatility=0.10,
                max_leverage=1.0,
                scaling_dampening=0.7,
            ),
            drawdown=DrawdownConfig(
                warning_threshold=-0.03,
                reduce_threshold=-0.07,
                critical_threshold=-0.10,
                kill_switch_threshold=-0.15,
            ),
            var=VaRConfig(
                confidence_levels=(0.95, 0.99, 0.999),
                monte_carlo_simulations=50_000,
            ),
            governance=GovernanceConfig(
                max_daily_var_pct=0.01,
                max_portfolio_var_pct=0.03,
            ),
        )

    @staticmethod
    def aggressive() -> RiskEngineConfig:
        """Wider limits for high-capacity, diversified strategies."""
        return RiskEngineConfig(
            exposure=ExposureConfig(
                max_gross_leverage=3.0,
                max_net_exposure_ratio=1.5,
                max_single_name_weight=0.20,
            ),
            volatility=VolatilityConfig(
                target_volatility=0.20,
                max_leverage=3.0,
            ),
            drawdown=DrawdownConfig(
                warning_threshold=-0.08,
                reduce_threshold=-0.15,
                critical_threshold=-0.20,
                kill_switch_threshold=-0.30,
            ),
            governance=GovernanceConfig(
                max_daily_var_pct=0.04,
                max_portfolio_var_pct=0.08,
            ),
        )
