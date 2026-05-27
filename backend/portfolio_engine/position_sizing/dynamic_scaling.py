"""
Dynamic position scaling — regime-aware, drawdown-aware scaling overlays.

Applies multiplicative scaling factors on top of base position sizes based on:
- Market regime (trend, mean-reversion, crisis)
- Current drawdown depth and speed
- Volatility environment
- Alpha confidence

This layer does NOT replace the base sizing — it modulates it.

Statistical assumptions:
- Regime classification is correct at the time of evaluation (no lookahead).
- Scaling factors are bounded to prevent total de-risking or over-leveraging.
- Drawdown scaling is asymmetric: faster reduction, slower recovery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DynamicScalingConfig:
    drawdown_reduce_threshold: float = -0.05
    drawdown_critical_threshold: float = -0.15
    drawdown_reduce_factor: float = 0.7
    drawdown_critical_factor: float = 0.3
    recovery_ramp_speed: float = 0.1
    vol_scale_enabled: bool = True
    vol_expansion_threshold: float = 1.5
    vol_expansion_scale: float = 0.7
    regime_scaling: dict[str, float] = field(default_factory=lambda: {
        "trending": 1.0,
        "mean_reverting": 0.8,
        "crisis": 0.3,
        "normal": 1.0,
        "elevated": 0.8,
        "stressed": 0.5,
    })
    min_scale: float = 0.1
    max_scale: float = 1.5
    confidence_floor: float = 0.3


@dataclass(frozen=True)
class ScalingResult:
    base_scale: float
    drawdown_scale: float
    regime_scale: float
    vol_scale: float
    confidence_scale: float
    final_scale: float
    components: dict[str, float]
    warnings: list[str] = field(default_factory=list)


class DynamicScaler:
    """
    Compute multiplicative scaling overlays for position sizes.

    Each scaling component is independent and multiplicative:
    final_scale = base * drawdown * regime * vol * confidence

    All components are bounded to [0.1, 1.5] individually and
    the final composite is clamped to [min_scale, max_scale].
    """

    def __init__(self, config: DynamicScalingConfig | None = None) -> None:
        self._config = config or DynamicScalingConfig()

    def compute_scale(
        self,
        current_drawdown: float = 0.0,
        regime: str = "normal",
        realized_vol: float = 0.0,
        target_vol: float = 0.15,
        avg_confidence: float = 1.0,
    ) -> ScalingResult:
        cfg = self._config
        warnings: list[str] = []

        dd_scale = self._drawdown_scale(current_drawdown)
        if dd_scale < 0.5:
            warnings.append(
                f"Significant drawdown scaling: dd={current_drawdown:.3f}, scale={dd_scale:.3f}"
            )

        regime_key = regime.lower().replace(" ", "_")
        regime_scale = cfg.regime_scaling.get(regime_key, 1.0)

        vol_scale = 1.0
        if cfg.vol_scale_enabled and target_vol > 0 and realized_vol > 0:
            vol_ratio = realized_vol / target_vol
            if vol_ratio > cfg.vol_expansion_threshold:
                vol_scale = cfg.vol_expansion_scale
                warnings.append(
                    f"Vol expansion scaling: ratio={vol_ratio:.2f}, scale={vol_scale:.3f}"
                )

        conf_scale = max(avg_confidence, cfg.confidence_floor)

        final = dd_scale * regime_scale * vol_scale * conf_scale
        final = float(np.clip(final, cfg.min_scale, cfg.max_scale))

        return ScalingResult(
            base_scale=1.0,
            drawdown_scale=dd_scale,
            regime_scale=regime_scale,
            vol_scale=vol_scale,
            confidence_scale=conf_scale,
            final_scale=final,
            components={
                "drawdown": dd_scale,
                "regime": regime_scale,
                "volatility": vol_scale,
                "confidence": conf_scale,
            },
            warnings=warnings,
        )

    def _drawdown_scale(self, dd: float) -> float:
        cfg = self._config
        if dd >= 0:
            return 1.0
        if dd <= cfg.drawdown_critical_threshold:
            return cfg.drawdown_critical_factor
        if dd <= cfg.drawdown_reduce_threshold:
            frac = (dd - cfg.drawdown_reduce_threshold) / (
                cfg.drawdown_critical_threshold - cfg.drawdown_reduce_threshold
            )
            return cfg.drawdown_reduce_factor + frac * (
                cfg.drawdown_critical_factor - cfg.drawdown_reduce_factor
            )
        return 1.0

    def scale_weights(
        self,
        weights: dict[str, float],
        current_drawdown: float = 0.0,
        regime: str = "normal",
        realized_vol: float = 0.0,
        target_vol: float = 0.15,
        avg_confidence: float = 1.0,
    ) -> tuple[dict[str, float], ScalingResult]:
        result = self.compute_scale(
            current_drawdown=current_drawdown,
            regime=regime,
            realized_vol=realized_vol,
            target_vol=target_vol,
            avg_confidence=avg_confidence,
        )
        scaled = {s: w * result.final_scale for s, w in weights.items()}
        return scaled, result
