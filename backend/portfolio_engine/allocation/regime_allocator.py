"""
Regime-aware allocation — adjusts portfolio construction based on market regime.

Maps regime classifications to allocation parameter overrides:
- Crisis → reduce leverage, tighten position limits, increase cash
- Trending → maintain normal or elevated exposure
- Mean-reverting → moderate exposure, shorter holding periods
- Normal → baseline allocation parameters

Statistical assumptions:
- Regime classification is available and reasonably accurate.
- Regime transitions are gradual enough for allocation adjustments to be timely.
- Regime persistence is sufficient to justify the allocation shift cost.

Known limitations:
- Regime detection lags true regime transitions → allocation changes arrive late.
- False regime signals cause unnecessary turnover and cost drag.
- The mapping from regime to parameters is heuristic, not optimized.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique

import numpy as np

logger = logging.getLogger(__name__)


@unique
class MarketRegime(Enum):
    NORMAL = "normal"
    TRENDING = "trending"
    MEAN_REVERTING = "mean_reverting"
    CRISIS = "crisis"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"


@dataclass(frozen=True)
class RegimeOverrides:
    leverage_multiplier: float = 1.0
    max_position_scale: float = 1.0
    cash_reserve_fraction: float = 0.0
    risk_budget_scale: float = 1.0
    turnover_limit_scale: float = 1.0
    preferred_optimizer: str = ""


DEFAULT_REGIME_MAP: dict[MarketRegime, RegimeOverrides] = {
    MarketRegime.NORMAL: RegimeOverrides(
        leverage_multiplier=1.0,
        max_position_scale=1.0,
        cash_reserve_fraction=0.0,
    ),
    MarketRegime.TRENDING: RegimeOverrides(
        leverage_multiplier=1.1,
        max_position_scale=1.0,
        cash_reserve_fraction=0.0,
        preferred_optimizer="mean_variance",
    ),
    MarketRegime.MEAN_REVERTING: RegimeOverrides(
        leverage_multiplier=0.8,
        max_position_scale=0.9,
        cash_reserve_fraction=0.05,
    ),
    MarketRegime.CRISIS: RegimeOverrides(
        leverage_multiplier=0.3,
        max_position_scale=0.5,
        cash_reserve_fraction=0.30,
        risk_budget_scale=0.5,
        turnover_limit_scale=0.5,
    ),
    MarketRegime.HIGH_VOLATILITY: RegimeOverrides(
        leverage_multiplier=0.6,
        max_position_scale=0.7,
        cash_reserve_fraction=0.10,
        risk_budget_scale=0.7,
    ),
    MarketRegime.LOW_VOLATILITY: RegimeOverrides(
        leverage_multiplier=1.2,
        max_position_scale=1.1,
        cash_reserve_fraction=0.0,
    ),
}


@dataclass(frozen=True)
class RegimeAllocationConfig:
    regime_map: dict[MarketRegime, RegimeOverrides] = field(
        default_factory=lambda: dict(DEFAULT_REGIME_MAP)
    )
    regime_transition_damping: float = 0.5
    min_regime_confidence: float = 0.5
    blend_with_neutral: bool = True


@dataclass(frozen=True)
class RegimeAllocationResult:
    regime: MarketRegime
    regime_confidence: float
    overrides: RegimeOverrides
    blended_leverage_multiplier: float
    blended_cash_reserve: float
    adjusted_weights: dict[str, float]
    original_weights: dict[str, float]
    warnings: list[str] = field(default_factory=list)


class RegimeAllocator:
    """
    Adjust allocation parameters based on detected market regime.

    Blends regime-specific overrides with neutral parameters based on
    regime confidence to prevent binary switching.
    """

    def __init__(self, config: RegimeAllocationConfig | None = None) -> None:
        self._config = config or RegimeAllocationConfig()
        self._last_regime: MarketRegime | None = None

    def allocate(
        self,
        weights: dict[str, float],
        regime: MarketRegime | str,
        regime_confidence: float = 1.0,
    ) -> RegimeAllocationResult:
        cfg = self._config
        warnings: list[str] = []

        if isinstance(regime, str):
            try:
                regime_enum = MarketRegime(regime.lower())
            except ValueError:
                warnings.append(f"Unknown regime '{regime}', defaulting to NORMAL")
                regime_enum = MarketRegime.NORMAL
        else:
            regime_enum = regime

        overrides = cfg.regime_map.get(regime_enum, RegimeOverrides())
        neutral = cfg.regime_map.get(MarketRegime.NORMAL, RegimeOverrides())

        confidence = float(np.clip(regime_confidence, 0.0, 1.0))
        if confidence < cfg.min_regime_confidence:
            warnings.append(
                f"Regime confidence {confidence:.3f} below threshold "
                f"{cfg.min_regime_confidence:.3f}, blending toward neutral"
            )

        if cfg.blend_with_neutral:
            blend = confidence
            blended_lev = neutral.leverage_multiplier + blend * (
                overrides.leverage_multiplier - neutral.leverage_multiplier
            )
            blended_cash = neutral.cash_reserve_fraction + blend * (
                overrides.cash_reserve_fraction - neutral.cash_reserve_fraction
            )
            blended_pos = neutral.max_position_scale + blend * (
                overrides.max_position_scale - neutral.max_position_scale
            )
        else:
            blended_lev = overrides.leverage_multiplier
            blended_cash = overrides.cash_reserve_fraction
            blended_pos = overrides.max_position_scale

        if self._last_regime and self._last_regime != regime_enum:
            warnings.append(
                f"Regime transition: {self._last_regime.value} → {regime_enum.value}"
            )
        self._last_regime = regime_enum

        investable_fraction = 1.0 - blended_cash
        adjusted = {}
        for symbol, w in weights.items():
            scaled = w * blended_lev * investable_fraction
            max_abs = overrides.max_position_scale * 0.25
            adjusted[symbol] = float(np.clip(scaled, -max_abs, max_abs))

        return RegimeAllocationResult(
            regime=regime_enum,
            regime_confidence=confidence,
            overrides=overrides,
            blended_leverage_multiplier=blended_lev,
            blended_cash_reserve=blended_cash,
            adjusted_weights=adjusted,
            original_weights=dict(weights),
            warnings=warnings,
        )
