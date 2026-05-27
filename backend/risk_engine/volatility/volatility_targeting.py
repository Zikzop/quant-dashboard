"""
Volatility targeting engine — scales leverage to maintain constant risk.

When realized volatility rises, the engine reduces leverage proportionally.
When volatility falls, it increases leverage — but with dampening to avoid
oscillatory overreaction from mean-reverting vol.

This is the core risk-budgeting mechanism. It separates the alpha signal
(direction) from the risk allocation (size), ensuring that position sizing
adapts to the current risk environment.

WARNING: Volatility targeting can amplify momentum crashes if vol drops
before the crash materializes. The dampening factor and floor/ceiling
constraints mitigate but do not eliminate this risk.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_engine.risk_config import VolatilityConfig
from risk_engine.volatility.realized_volatility import RealizedVolatilityEngine

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VolTargetOutput:
    """Volatility targeting decision."""

    target_vol: float
    realized_vol: float
    raw_leverage: float
    dampened_leverage: float
    final_leverage: float
    scaling_factor: float
    vol_regime: str
    rebalance_needed: bool


class VolatilityTargetingEngine:
    """
    Dynamically scales portfolio leverage to target a fixed volatility level.

    Steps:
    1. Estimate realized vol from recent returns
    2. Compute raw leverage = target_vol / realized_vol
    3. Apply dampening to reduce whipsawing
    4. Clamp to [min_leverage, max_leverage]
    5. Signal rebalance only if deviation exceeds threshold
    """

    def __init__(self, config: VolatilityConfig | None = None) -> None:
        self._config = config or VolatilityConfig()
        self._vol_engine = RealizedVolatilityEngine(
            lookback_days=self._config.vol_lookback_days,
            ewm_halflife=self._config.vol_halflife_days,
        )
        self._prev_leverage: float | None = None

    def compute(
        self,
        returns: pd.Series,
        current_leverage: float = 1.0,
    ) -> VolTargetOutput:
        vol_est = self._vol_engine.estimate_from_returns(returns)
        realized = vol_est.annualized_composite

        realized = np.clip(realized, self._config.vol_floor, self._config.vol_ceiling)

        raw_leverage = self._config.target_volatility / max(realized, 1e-6)

        if self._prev_leverage is not None:
            dampened = (
                self._config.scaling_dampening * self._prev_leverage
                + (1.0 - self._config.scaling_dampening) * raw_leverage
            )
        else:
            dampened = raw_leverage

        final = float(np.clip(dampened, self._config.min_leverage, self._config.max_leverage))
        self._prev_leverage = final

        deviation = abs(final - current_leverage) / max(current_leverage, 1e-6)
        rebalance = deviation > self._config.rebalance_threshold

        regime = self._classify_vol_regime(realized)

        return VolTargetOutput(
            target_vol=self._config.target_volatility,
            realized_vol=realized,
            raw_leverage=raw_leverage,
            dampened_leverage=dampened,
            final_leverage=final,
            scaling_factor=final / max(current_leverage, 1e-6),
            vol_regime=regime,
            rebalance_needed=rebalance,
        )

    def _classify_vol_regime(self, realized: float) -> str:
        target = self._config.target_volatility
        if realized < target * 0.5:
            return "LOW_VOL"
        elif realized < target * 1.0:
            return "NORMAL_VOL"
        elif realized < target * 1.5:
            return "HIGH_VOL"
        elif realized < target * 2.5:
            return "VERY_HIGH_VOL"
        else:
            return "EXTREME_VOL"
