"""
Dynamic scaling — regime-aware position sizing adjustments.

Beyond simple vol-targeting, dynamic scaling considers regime context:
- Reduce exposure during regime transitions (high uncertainty)
- Scale down when vol-of-vol is elevated (unstable risk environment)
- Apply asymmetric scaling: faster to reduce than to increase
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from risk_engine.risk_config import RiskRegime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScalingDecision:
    """Dynamic scaling output."""

    base_scale: float
    regime_adjustment: float
    vol_of_vol_adjustment: float
    asymmetry_adjustment: float
    final_scale: float
    risk_regime: RiskRegime
    rationale: str


class DynamicScalingEngine:
    """
    Applies regime-aware adjustments on top of volatility targeting.

    The key principle is asymmetric speed: the engine reduces exposure
    faster than it increases it. This prevents capital destruction during
    rapid regime shifts while still allowing gradual re-engagement.
    """

    def __init__(
        self,
        reduction_speed: float = 0.8,
        increase_speed: float = 0.3,
        vol_of_vol_lookback: int = 20,
    ) -> None:
        self._reduction_speed = reduction_speed
        self._increase_speed = increase_speed
        self._vov_lookback = vol_of_vol_lookback
        self._prev_scale: float = 1.0

    def compute(
        self,
        target_scale: float,
        returns: pd.Series,
        risk_regime: RiskRegime = RiskRegime.NORMAL,
    ) -> ScalingDecision:
        regime_adj = self._regime_adjustment(risk_regime)

        vov_adj = self._vol_of_vol_adjustment(returns)

        desired = target_scale * regime_adj * vov_adj

        if desired < self._prev_scale:
            speed = self._reduction_speed
        else:
            speed = self._increase_speed

        final = self._prev_scale + speed * (desired - self._prev_scale)
        final = float(np.clip(final, 0.0, 2.0))

        rationale = (
            f"Regime={risk_regime.value} adj={regime_adj:.2f}, "
            f"VoV adj={vov_adj:.2f}, speed={'reduce' if desired < self._prev_scale else 'increase'}"
        )

        self._prev_scale = final

        return ScalingDecision(
            base_scale=target_scale,
            regime_adjustment=regime_adj,
            vol_of_vol_adjustment=vov_adj,
            asymmetry_adjustment=speed,
            final_scale=final,
            risk_regime=risk_regime,
            rationale=rationale,
        )

    @staticmethod
    def _regime_adjustment(regime: RiskRegime) -> float:
        return {
            RiskRegime.NORMAL: 1.0,
            RiskRegime.ELEVATED: 0.85,
            RiskRegime.STRESSED: 0.60,
            RiskRegime.CRISIS: 0.30,
        }[regime]

    def _vol_of_vol_adjustment(self, returns: pd.Series) -> float:
        if len(returns) < self._vov_lookback + 5:
            return 1.0

        rolling_vol = returns.rolling(5).std().dropna()
        if len(rolling_vol) < self._vov_lookback:
            return 1.0

        recent_vov = rolling_vol.iloc[-self._vov_lookback:]
        vov = float(recent_vov.std() / max(recent_vov.mean(), 1e-6))

        if vov < 0.5:
            return 1.0
        elif vov < 1.0:
            return 0.9
        elif vov < 2.0:
            return 0.75
        else:
            return 0.5
