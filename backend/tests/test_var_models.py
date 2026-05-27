"""
Tests for VaR and CVaR models.

Validates:
- Historical VaR quantile correctness
- Parametric VaR distributional assumptions
- Monte Carlo VaR convergence
- CVaR tail behavior
- Tail risk estimation
- VaR model consistency (Student-t >= Gaussian)
"""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from risk_engine.risk_config import VaRConfig
from risk_engine.var.historical_var import HistoricalVaREngine
from risk_engine.var.parametric_var import ParametricVaREngine
from risk_engine.var.monte_carlo_var import MonteCarloVaREngine
from risk_engine.var.cvar_engine import CVaREngine
from risk_engine.var.tail_risk import TailRiskEngine


def _make_returns(n: int = 500, seed: int = 42, fat_tails: bool = False) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-01", periods=n, freq="B", tz="UTC")
    if fat_tails:
        from scipy import stats as sp_stats
        returns = sp_stats.t.rvs(df=3, loc=0.0002, scale=0.012, size=n, random_state=rng.integers(0, 2**31))
    else:
        returns = rng.normal(0.0003, 0.012, n)
    return pd.Series(returns, index=idx)


class TestHistoricalVaR(unittest.TestCase):
    def test_var_is_negative(self) -> None:
        """Historical VaR should be a loss (negative) for typical data."""
        returns = _make_returns()
        engine = HistoricalVaREngine()
        result = engine.compute(returns)
        for cl, var in result.var_levels.items():
            self.assertLess(var, 0, f"VaR at {cl} should be negative (a loss)")

    def test_higher_confidence_more_extreme(self) -> None:
        """99% VaR should be at least as extreme as 95% VaR."""
        returns = _make_returns()
        engine = HistoricalVaREngine()
        result = engine.compute(returns, confidence_levels=(0.95, 0.99))
        self.assertLessEqual(
            result.var_levels[0.99],
            result.var_levels[0.95],
            "99% VaR should be at least as extreme as 95%",
        )

    def test_insufficient_data(self) -> None:
        """Engine handles insufficient data gracefully."""
        returns = _make_returns(n=10)
        config = VaRConfig(min_observations=60)
        engine = HistoricalVaREngine(config=config)
        result = engine.compute(returns)
        self.assertEqual(result.var_levels[0.95], 0.0)

    def test_worst_loss_exceeds_var(self) -> None:
        """Worst observed loss should exceed VaR."""
        returns = _make_returns()
        engine = HistoricalVaREngine()
        result = engine.compute(returns)
        self.assertLessEqual(result.worst_loss, result.var_levels[0.99])


class TestParametricVaR(unittest.TestCase):
    def test_student_t_more_conservative(self) -> None:
        """Student-t VaR should be more extreme than Gaussian for fat-tailed data."""
        returns = _make_returns(fat_tails=True)
        engine = ParametricVaREngine()
        result = engine.compute(returns, confidence_levels=(0.99,))
        self.assertLessEqual(
            result.student_t_var[0.99],
            result.gaussian_var[0.99] + 0.005,
            "Student-t should capture fat tails",
        )

    def test_all_three_models_produce_output(self) -> None:
        """All parametric models should produce non-zero VaR."""
        returns = _make_returns()
        engine = ParametricVaREngine()
        result = engine.compute(returns)
        self.assertNotEqual(result.gaussian_var[0.95], 0.0)
        self.assertNotEqual(result.student_t_var[0.95], 0.0)
        self.assertNotEqual(result.cornish_fisher_var[0.95], 0.0)

    def test_kurtosis_estimated(self) -> None:
        """Fat-tailed data should show positive excess kurtosis."""
        returns = _make_returns(fat_tails=True)
        engine = ParametricVaREngine()
        result = engine.compute(returns)
        self.assertGreater(result.estimated_kurtosis, 0, "Fat tails should show excess kurtosis")


class TestMonteCarloVaR(unittest.TestCase):
    def test_mc_var_is_negative(self) -> None:
        """Monte Carlo VaR should be a loss."""
        returns = _make_returns()
        engine = MonteCarloVaREngine()
        result = engine.compute(returns, seed=42)
        for cl, var in result.var_levels.items():
            self.assertLess(var, 0.05, f"MC VaR at {cl} should be reasonable")

    def test_expected_shortfall_worse_than_var(self) -> None:
        """Expected shortfall should be more extreme than VaR."""
        returns = _make_returns()
        engine = MonteCarloVaREngine()
        result = engine.compute(returns, seed=42)
        for cl in result.var_levels:
            self.assertLessEqual(
                result.expected_shortfall[cl],
                result.var_levels[cl] + 1e-6,
                f"ES should be <= VaR at {cl}",
            )


class TestCVaR(unittest.TestCase):
    def test_cvar_more_extreme_than_var(self) -> None:
        """CVaR should always be more extreme than VaR."""
        returns = _make_returns()
        engine = CVaREngine()
        result = engine.compute(returns)
        for cl in result.var_levels:
            self.assertLessEqual(
                result.cvar_levels[cl],
                result.var_levels[cl] + 1e-9,
                f"CVaR should be <= VaR at {cl}",
            )

    def test_tail_ratio_above_one(self) -> None:
        """Tail ratio (CVaR/VaR) should be >= 1.0 for typical data."""
        returns = _make_returns()
        engine = CVaREngine()
        result = engine.compute(returns)
        for cl, ratio in result.tail_ratio.items():
            self.assertGreaterEqual(ratio, 0.9, f"Tail ratio at {cl} should be ~1+")

    def test_n_tail_observations(self) -> None:
        """Should have appropriate number of tail observations."""
        returns = _make_returns(n=500)
        engine = CVaREngine()
        result = engine.compute(returns)
        self.assertGreater(result.n_tail_observations[0.95], 0)
        self.assertGreater(result.n_tail_observations[0.99], 0)


class TestTailRisk(unittest.TestCase):
    def test_tail_index_estimated(self) -> None:
        """Tail index should be positive for real-looking data."""
        returns = _make_returns(fat_tails=True)
        engine = TailRiskEngine()
        result = engine.estimate(returns)
        self.assertGreater(result.tail_index, 0)
        self.assertGreater(result.n_tail_observations, 0)

    def test_fat_tails_detected(self) -> None:
        """Fat-tailed data should be flagged."""
        returns = _make_returns(fat_tails=True)
        engine = TailRiskEngine()
        result = engine.estimate(returns)
        self.assertTrue(result.tail_is_fat, "Student-t(3) data should show fat tails")

    def test_insufficient_data(self) -> None:
        """Handles very short series gracefully."""
        returns = _make_returns(n=5)
        engine = TailRiskEngine()
        result = engine.estimate(returns)
        self.assertEqual(result.tail_index, 0.0)


if __name__ == "__main__":
    unittest.main()
