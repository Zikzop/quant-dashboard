"""
Transaction-cost-aware rebalancing.

Adjusts target weights to account for expected transaction costs,
producing net-of-cost optimal rebalancing targets. Only trades when
the expected alpha benefit exceeds the cost.

The "no-trade zone" approach: for each asset, compute the band around
the target weight within which trading is not cost-effective.

Statistical assumptions:
- Transaction costs are modeled as a fixed per-unit cost + market impact.
- The no-trade zone width is proportional to cost / (expected alpha decay).
- Alpha signal decay rate determines the urgency of rebalancing.

References:
- Almgren & Chriss (2000) for market impact modeling
- Garleanu & Pedersen (2013) for dynamic portfolio choice with costs
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransactionAwareConfig:
    fixed_cost_bps: float = 5.0
    impact_coefficient: float = 0.1
    impact_exponent: float = 0.5
    alpha_decay_halflife_days: float = 20.0
    risk_aversion: float = 2.5
    min_trade_threshold_bps: float = 2.0


@dataclass(frozen=True)
class TransactionAwareResult:
    optimal_weights: dict[str, float]
    no_trade_zones: dict[str, tuple[float, float]]
    trades_suppressed: list[str]
    trades_executed: list[str]
    estimated_total_cost_bps: float
    net_benefit_bps: float
    warnings: list[str] = field(default_factory=list)


class TransactionAwareRebalancer:
    """
    Compute cost-aware rebalancing targets using no-trade zones.

    For each asset, computes a band around the target weight.
    If the current weight falls within this band, no trade is executed.
    """

    def __init__(self, config: TransactionAwareConfig | None = None) -> None:
        self._config = config or TransactionAwareConfig()

    def rebalance(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        asset_volatilities: dict[str, float] | None = None,
        asset_alphas: dict[str, float] | None = None,
    ) -> TransactionAwareResult:
        cfg = self._config
        warnings: list[str] = []

        all_symbols = set(current_weights) | set(target_weights)
        optimal = {}
        zones: dict[str, tuple[float, float]] = {}
        suppressed = []
        executed = []
        total_cost = 0.0
        total_benefit = 0.0

        for symbol in all_symbols:
            w_curr = current_weights.get(symbol, 0.0)
            w_target = target_weights.get(symbol, 0.0)
            vol = (asset_volatilities or {}).get(symbol, 0.15)
            alpha = (asset_alphas or {}).get(symbol, 0.0)

            zone_width = self._compute_zone_width(vol, alpha)
            zone_lower = w_target - zone_width
            zone_upper = w_target + zone_width
            zones[symbol] = (zone_lower, zone_upper)

            if zone_lower <= w_curr <= zone_upper:
                optimal[symbol] = w_curr
                suppressed.append(symbol)
            else:
                delta = w_target - w_curr
                trade_cost = self._estimate_cost(abs(delta), vol)
                trade_benefit = abs(alpha) * abs(delta) * 10_000

                if trade_benefit > trade_cost + cfg.min_trade_threshold_bps:
                    optimal[symbol] = w_target
                    executed.append(symbol)
                    total_cost += trade_cost
                    total_benefit += trade_benefit
                else:
                    partial = w_curr + 0.5 * delta
                    optimal[symbol] = partial
                    suppressed.append(symbol)
                    warnings.append(
                        f"{symbol}: partial rebalance (cost={trade_cost:.1f}bps "
                        f"> benefit={trade_benefit:.1f}bps)"
                    )

        net_benefit = total_benefit - total_cost

        return TransactionAwareResult(
            optimal_weights=optimal,
            no_trade_zones=zones,
            trades_suppressed=suppressed,
            trades_executed=executed,
            estimated_total_cost_bps=total_cost,
            net_benefit_bps=net_benefit,
            warnings=warnings,
        )

    def _compute_zone_width(self, vol: float, alpha: float) -> float:
        cfg = self._config
        decay_rate = np.log(2) / max(cfg.alpha_decay_halflife_days, 1.0)
        alpha_urgency = max(abs(alpha) * decay_rate, 1e-6)
        cost_factor = (cfg.fixed_cost_bps / 10_000) / alpha_urgency
        vol_factor = vol * 0.1
        width = np.sqrt(cost_factor) * vol_factor / cfg.risk_aversion
        return float(np.clip(width, 0.001, 0.05))

    def _estimate_cost(self, trade_size: float, vol: float) -> float:
        cfg = self._config
        linear = trade_size * cfg.fixed_cost_bps
        impact = cfg.impact_coefficient * (trade_size ** cfg.impact_exponent) * vol * 10_000
        return linear + impact
