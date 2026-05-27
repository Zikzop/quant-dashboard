"""
Implementation shortfall analysis.

Implementation shortfall (IS) measures the total cost of executing a decision,
defined as the difference between the paper return and the actual return.

IS = (decision price - execution price) / decision price * direction

Components:
- Delay cost: price movement between decision and first fill
- Trading cost: spread + impact during execution
- Opportunity cost: unfilled portion times subsequent price movement

References:
- Perold (1988): "The Implementation Shortfall"
- Almgren & Chriss (2000): Optimal execution framework
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

from execution_engine.execution_base import ExecutionResult, FillEvent, OrderSide

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ISReport:
    total_is_bps: float
    delay_cost_bps: float
    trading_cost_bps: float
    opportunity_cost_bps: float
    fill_ratio: float
    decision_price: float
    avg_execution_price: float
    closing_price: float
    notional_traded: float
    notional_target: float
    warnings: list[str] = field(default_factory=list)


class ImplementationShortfallAnalyzer:
    """
    Compute implementation shortfall decomposition.
    """

    def analyze(
        self,
        result: ExecutionResult,
        decision_price: float,
        closing_price: float | None = None,
    ) -> ISReport:
        warnings: list[str] = []

        parent = result.parent_order
        side_sign = 1.0 if parent.side == OrderSide.BUY else -1.0

        if decision_price <= 0:
            warnings.append("Invalid decision price")
            decision_price = result.avg_fill_price or 1.0

        fills = [f for c in result.child_orders for f in c.fill_events]
        if not fills:
            return ISReport(
                total_is_bps=0.0, delay_cost_bps=0.0, trading_cost_bps=0.0,
                opportunity_cost_bps=0.0, fill_ratio=0.0,
                decision_price=decision_price, avg_execution_price=0.0,
                closing_price=closing_price or decision_price,
                notional_traded=0.0, notional_target=parent.total_quantity * decision_price,
                warnings=warnings + ["No fills"],
            )

        first_fill_price = fills[0].fill_price

        total_qty = sum(f.quantity_filled for f in fills)
        total_notional = sum(f.notional for f in fills)
        avg_exec = total_notional / total_qty if total_qty > 0 else decision_price

        delay_cost = side_sign * (first_fill_price - decision_price) / decision_price * 10_000

        trading_cost = side_sign * (avg_exec - first_fill_price) / decision_price * 10_000

        unfilled = parent.total_quantity - total_qty
        close = closing_price or avg_exec
        if unfilled > 0 and parent.total_quantity > 0:
            opp_cost = (
                side_sign * (close - decision_price) / decision_price
                * (unfilled / parent.total_quantity) * 10_000
            )
        else:
            opp_cost = 0.0

        total_is = delay_cost + trading_cost + opp_cost

        fill_ratio = total_qty / parent.total_quantity if parent.total_quantity > 0 else 0.0

        if total_is > 50:
            warnings.append(
                f"High implementation shortfall ({total_is:.1f} bps). "
                "Consider more aggressive algorithm."
            )

        return ISReport(
            total_is_bps=total_is,
            delay_cost_bps=delay_cost,
            trading_cost_bps=trading_cost,
            opportunity_cost_bps=opp_cost,
            fill_ratio=fill_ratio,
            decision_price=decision_price,
            avg_execution_price=avg_exec,
            closing_price=close,
            notional_traded=total_notional,
            notional_target=parent.total_quantity * decision_price,
            warnings=warnings,
        )
