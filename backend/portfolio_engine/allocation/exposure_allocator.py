"""
Exposure allocation — translates target weights into exposure-adjusted positions.

Handles the conversion from theoretical portfolio weights to exposure-aware
allocations that account for leverage, gross/net constraints, and
per-asset volatility differences.

Statistical assumptions:
- Exposure is measured in notional terms relative to NAV.
- Volatility-adjusted exposure normalizes heterogeneous asset risk profiles.
- Leverage is computed as gross notional / NAV.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExposureConfig:
    max_gross_leverage: float = 2.0
    max_net_exposure: float = 1.0
    target_gross_leverage: float = 1.0
    vol_adjust_exposure: bool = True
    max_single_exposure: float = 0.20


@dataclass(frozen=True)
class ExposureAllocationResult:
    adjusted_weights: dict[str, float]
    gross_leverage: float
    net_exposure: float
    leverage_scaled: bool
    per_asset_exposure: dict[str, float]
    warnings: list[str] = field(default_factory=list)


class ExposureAllocator:
    """
    Adjust portfolio weights to meet exposure constraints.

    Scales the weight vector to stay within gross/net leverage bounds
    while optionally adjusting for per-asset volatility differences.
    """

    def __init__(self, config: ExposureConfig | None = None) -> None:
        self._config = config or ExposureConfig()

    def allocate(
        self,
        target_weights: dict[str, float],
        asset_volatilities: dict[str, float] | None = None,
        nav: float = 1_000_000.0,
    ) -> ExposureAllocationResult:
        cfg = self._config
        warnings: list[str] = []

        if not target_weights:
            return ExposureAllocationResult(
                adjusted_weights={}, gross_leverage=0.0, net_exposure=0.0,
                leverage_scaled=False, per_asset_exposure={},
                warnings=["Empty weight vector"],
            )

        weights = dict(target_weights)

        if cfg.vol_adjust_exposure and asset_volatilities:
            target_vol = 0.15
            for symbol in list(weights.keys()):
                vol = asset_volatilities.get(symbol, target_vol)
                if vol > 0:
                    vol_ratio = target_vol / vol
                    weights[symbol] *= vol_ratio

        for symbol in list(weights.keys()):
            if abs(weights[symbol]) > cfg.max_single_exposure:
                old_w = weights[symbol]
                weights[symbol] = np.sign(old_w) * cfg.max_single_exposure
                warnings.append(
                    f"{symbol}: exposure capped from {old_w:.4f} to {weights[symbol]:.4f}"
                )

        gross = sum(abs(w) for w in weights.values())
        net = sum(weights.values())
        leverage_scaled = False

        if gross > cfg.max_gross_leverage:
            scale = cfg.max_gross_leverage / gross
            weights = {s: w * scale for s, w in weights.items()}
            gross = cfg.max_gross_leverage
            leverage_scaled = True
            warnings.append(
                f"Gross leverage scaled to max {cfg.max_gross_leverage:.2f}"
            )

        if abs(net) > cfg.max_net_exposure:
            scale = cfg.max_net_exposure / abs(net)
            weights = {s: w * scale for s, w in weights.items()}
            net = np.sign(net) * cfg.max_net_exposure
            gross = sum(abs(w) for w in weights.values())
            leverage_scaled = True
            warnings.append(
                f"Net exposure scaled to max {cfg.max_net_exposure:.2f}"
            )

        per_asset = {s: w * nav for s, w in weights.items()}

        return ExposureAllocationResult(
            adjusted_weights=weights,
            gross_leverage=gross,
            net_exposure=sum(weights.values()),
            leverage_scaled=leverage_scaled,
            per_asset_exposure=per_asset,
            warnings=warnings,
        )
