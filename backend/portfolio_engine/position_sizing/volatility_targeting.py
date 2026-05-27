"""
Volatility targeting position sizing.

Scales position sizes to achieve a target portfolio volatility.
Uses exponentially weighted or rolling realized volatility estimates.

Statistical assumptions:
- Volatility is estimated from historical returns (backward-looking only).
- EWM half-life controls recency bias: shorter = more reactive, noisier.
- Scaling is dampened to avoid excessive turnover from vol spikes.
- Floor/ceiling bounds prevent pathological leverage in extreme regimes.

Known limitations:
- Volatility clustering means realized vol lags regime transitions.
- Variance targeting assumes vol is predictable — weaker during jumps.
- Leverage bounds can truncate position sizes during high-vol regimes,
  potentially causing the portfolio to miss mean-reversion opportunities.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VolTargetConfig:
    target_volatility: float = 0.15
    lookback_days: int = 60
    ewm_halflife: int = 20
    min_leverage: float = 0.1
    max_leverage: float = 2.0
    dampening: float = 0.5
    vol_floor: float = 0.05
    vol_ceiling: float = 0.80
    annualization_factor: float = 252.0
    min_observations: int = 20


@dataclass(frozen=True)
class VolTargetResult:
    raw_leverage: float
    dampened_leverage: float
    final_leverage: float
    realized_vol: float
    target_vol: float
    scaling_factor: float
    capped: bool
    warnings: list[str] = field(default_factory=list)


class VolatilityTargetSizer:
    """
    Scale portfolio weights to achieve target annualized volatility.

    Uses exponentially weighted realized vol with dampening to smooth
    leverage adjustments and reduce turnover.
    """

    def __init__(self, config: VolTargetConfig | None = None) -> None:
        self._config = config or VolTargetConfig()

    def compute_leverage(
        self,
        returns: pd.Series,
        current_leverage: float = 1.0,
    ) -> VolTargetResult:
        """
        Compute target leverage from return history.

        Parameters
        ----------
        returns : daily portfolio/asset returns, backward-looking only
        current_leverage : existing portfolio leverage for dampening
        """
        cfg = self._config
        warnings: list[str] = []

        if len(returns) < cfg.min_observations:
            warnings.append(
                f"Insufficient history ({len(returns)} < {cfg.min_observations}), "
                "defaulting to min leverage"
            )
            return VolTargetResult(
                raw_leverage=cfg.min_leverage,
                dampened_leverage=cfg.min_leverage,
                final_leverage=cfg.min_leverage,
                realized_vol=0.0,
                target_vol=cfg.target_volatility,
                scaling_factor=cfg.min_leverage,
                capped=True,
                warnings=warnings,
            )

        clean = returns.dropna().iloc[-cfg.lookback_days:]
        ewm_var = clean.ewm(halflife=cfg.ewm_halflife, min_periods=cfg.min_observations).var()
        if ewm_var.empty or ewm_var.iloc[-1] <= 0:
            warnings.append("EWM variance non-positive, defaulting to min leverage")
            return VolTargetResult(
                raw_leverage=cfg.min_leverage,
                dampened_leverage=cfg.min_leverage,
                final_leverage=cfg.min_leverage,
                realized_vol=0.0,
                target_vol=cfg.target_volatility,
                scaling_factor=cfg.min_leverage,
                capped=True,
                warnings=warnings,
            )

        realized_vol = float(np.sqrt(ewm_var.iloc[-1] * cfg.annualization_factor))
        realized_vol = np.clip(realized_vol, cfg.vol_floor, cfg.vol_ceiling)

        raw_leverage = cfg.target_volatility / realized_vol

        dampened = current_leverage + cfg.dampening * (raw_leverage - current_leverage)

        final = float(np.clip(dampened, cfg.min_leverage, cfg.max_leverage))
        capped = abs(final - dampened) > 1e-6

        if capped:
            warnings.append(
                f"Leverage capped: raw={raw_leverage:.3f}, "
                f"dampened={dampened:.3f}, final={final:.3f}"
            )

        if realized_vol > 2 * cfg.target_volatility:
            warnings.append(
                f"Realized vol ({realized_vol:.3f}) > 2x target ({cfg.target_volatility:.3f}). "
                "Significant de-leveraging in effect."
            )

        return VolTargetResult(
            raw_leverage=raw_leverage,
            dampened_leverage=dampened,
            final_leverage=final,
            realized_vol=realized_vol,
            target_vol=cfg.target_volatility,
            scaling_factor=final,
            capped=capped,
            warnings=warnings,
        )

    def scale_weights(
        self,
        weights: dict[str, float],
        returns: pd.Series,
        current_leverage: float = 1.0,
    ) -> tuple[dict[str, float], VolTargetResult]:
        """Scale a weight vector by the vol-target leverage factor."""
        result = self.compute_leverage(returns, current_leverage)
        current_gross = sum(abs(w) for w in weights.values())
        if current_gross < 1e-12:
            return weights, result

        scale = result.final_leverage / current_gross
        scaled = {s: w * scale for s, w in weights.items()}
        return scaled, result


def inverse_volatility_weights(
    volatilities: dict[str, float],
    vol_floor: float = 0.01,
) -> dict[str, float]:
    """
    Compute inverse-volatility weights.

    Higher vol assets get lower weight. Weights sum to 1.0.
    Volatility is floored to prevent numerical instability.
    """
    inv_vols = {}
    for symbol, vol in volatilities.items():
        safe_vol = max(vol, vol_floor)
        inv_vols[symbol] = 1.0 / safe_vol

    total = sum(inv_vols.values())
    if total < 1e-12:
        n = len(volatilities)
        return {s: 1.0 / n for s in volatilities} if n > 0 else {}

    return {s: iv / total for s, iv in inv_vols.items()}
