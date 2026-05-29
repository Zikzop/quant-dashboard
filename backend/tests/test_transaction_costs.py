"""
Tests for transaction cost models.

Validates:
- Commission calculations are correct
- Spread costs scale with volatility
- Slippage costs scale with participation
- Fee calculations match expected values
- Composite cost model integrates correctly
"""

from __future__ import annotations

import unittest

import numpy as np

from backtesting.transaction_costs.commission_models import (
    TieredCommission,
    FixedCommission,
    PercentageCommission,
    ZeroCommission,
)
from backtesting.transaction_costs.spread_costs import SpreadCostModel
from backtesting.transaction_costs.slippage_costs import SlippageCostModel
from backtesting.transaction_costs.fee_models import (
    RegulatoryFees,
    BorrowCost,
    CompositeCostModel,
)


class TestCommissionModels(unittest.TestCase):
    def test_tiered_commission(self) -> None:
        model = TieredCommission(per_share=0.005, min_per_order=1.0, max_pct=0.005)
        comm = model.calculate(1000, 50.0)
        self.assertAlmostEqual(comm, 5.0)

    def test_tiered_commission_minimum(self) -> None:
        model = TieredCommission(per_share=0.005, min_per_order=1.0)
        comm = model.calculate(10, 50.0)
        self.assertAlmostEqual(comm, 1.0)

    def test_tiered_commission_cap(self) -> None:
        model = TieredCommission(per_share=0.10, min_per_order=1.0, max_pct=0.005)
        comm = model.calculate(1000, 10.0)
        cap = 1000 * 10 * 0.005
        self.assertAlmostEqual(comm, cap)

    def test_fixed_commission(self) -> None:
        model = FixedCommission(per_order=7.0)
        self.assertAlmostEqual(model.calculate(100, 50), 7.0)
        self.assertAlmostEqual(model.calculate(10000, 50), 7.0)

    def test_percentage_commission(self) -> None:
        model = PercentageCommission(pct=0.001)
        comm = model.calculate(100, 50.0)
        self.assertAlmostEqual(comm, 5.0)

    def test_zero_commission(self) -> None:
        model = ZeroCommission()
        self.assertEqual(model.calculate(1000, 100), 0.0)


class TestSpreadCosts(unittest.TestCase):
    def test_spread_cost_positive(self) -> None:
        model = SpreadCostModel()
        cost = model.estimate(100, 1000, 0.2)
        self.assertGreater(cost, 0)

    def test_spread_increases_with_vol(self) -> None:
        model = SpreadCostModel()
        low = model.estimate(100, 1000, 0.05)
        high = model.estimate(100, 1000, 0.50)
        self.assertGreater(high, low)

    def test_spread_bps_diagnostic(self) -> None:
        model = SpreadCostModel(base_spread_bps=5, vol_multiplier=2)
        bps = model.spread_bps_at_vol(0.20)
        self.assertGreater(bps, 5)


class TestSlippageCosts(unittest.TestCase):
    def test_slippage_positive(self) -> None:
        model = SlippageCostModel()
        cost = model.estimate(100, 1000, 0.2, 50000)
        self.assertGreater(cost, 0)

    def test_slippage_scales_with_participation(self) -> None:
        model = SlippageCostModel()
        small = model.estimate(100, 100, 0.2, 100000)
        large = model.estimate(100, 50000, 0.2, 100000)
        self.assertGreater(large, small)

    def test_marginal_cost_positive(self) -> None:
        model = SlippageCostModel()
        mc = model.marginal_cost(100, 1000, 0.2, 50000)
        self.assertGreater(mc, 0)


class TestFeeModels(unittest.TestCase):
    def test_sec_fee_on_sells_only(self) -> None:
        fees = RegulatoryFees()
        buy_fees = fees.calculate(1000, 50, is_sell=False)
        sell_fees = fees.calculate(1000, 50, is_sell=True)
        self.assertGreater(sell_fees, buy_fees)

    def test_borrow_cost_long_is_zero(self) -> None:
        borrow = BorrowCost()
        self.assertEqual(borrow.daily_cost(50000), 0.0)

    def test_borrow_cost_short(self) -> None:
        borrow = BorrowCost(annual_rate_bps=100)
        cost = borrow.daily_cost(-100000)
        self.assertGreater(cost, 0)
        expected = 100000 * 0.01 / 252
        self.assertAlmostEqual(cost, expected, places=2)

    def test_composite_cost(self) -> None:
        model = CompositeCostModel()
        cost = model.total_cost(1000, 50.0, volatility=0.2, is_sell=True)
        self.assertGreater(cost, 0)

    def test_composite_cost_increases_with_vol(self) -> None:
        model = CompositeCostModel()
        low = model.total_cost(1000, 50.0, volatility=0.05)
        high = model.total_cost(1000, 50.0, volatility=0.50)
        self.assertGreater(high, low)


if __name__ == "__main__":
    unittest.main()
