"""
VaR diagnostic report — multi-model comparison and backtesting.

Comparing VaR estimates across models (Historical, Gaussian, Student-t,
Cornish-Fisher, Monte Carlo) reveals model risk. If models disagree
significantly, the risk estimate is unreliable.

The report also includes VaR backtesting: how many times did actual
losses exceed the VaR estimate? If violations exceed the expected
rate, the model is miscalibrated.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class VaRDiagnosticReport:
    """Multi-model VaR comparison and backtesting report."""

    confidence_level: float = 0.99
    historical_var: float = 0.0
    gaussian_var: float = 0.0
    student_t_var: float = 0.0
    cornish_fisher_var: float = 0.0
    monte_carlo_var: float = 0.0
    cvar: float = 0.0
    tail_index: float = 0.0
    model_spread: float = 0.0
    n_violations: int = 0
    expected_violations: float = 0.0
    violation_ratio: float = 0.0
    n_observations: int = 0
    kupiec_pvalue: float = 0.0

    def __post_init__(self) -> None:
        models = [
            self.historical_var,
            self.gaussian_var,
            self.student_t_var,
            self.cornish_fisher_var,
            self.monte_carlo_var,
        ]
        nonzero = [m for m in models if m != 0.0]
        if len(nonzero) >= 2:
            self.model_spread = max(nonzero) - min(nonzero)

    def summary_text(self) -> str:
        lines = [
            f"=== VaR DIAGNOSTIC REPORT ({self.confidence_level:.0%} confidence) ===",
            "",
            "--- MODEL COMPARISON ---",
            f"  Historical VaR:      {self.historical_var:+.4f}",
            f"  Gaussian VaR:        {self.gaussian_var:+.4f}",
            f"  Student-t VaR:       {self.student_t_var:+.4f}",
            f"  Cornish-Fisher VaR:  {self.cornish_fisher_var:+.4f}",
            f"  Monte Carlo VaR:     {self.monte_carlo_var:+.4f}",
            f"  CVaR (ES):           {self.cvar:+.4f}",
            "",
            f"  Model Spread:        {self.model_spread:.4f}",
            f"  Tail Index (Hill):   {self.tail_index:.2f}",
            "",
            "--- BACKTESTING ---",
            f"  Observations:        {self.n_observations}",
            f"  VaR Violations:      {self.n_violations}",
            f"  Expected Violations: {self.expected_violations:.1f}",
            f"  Violation Ratio:     {self.violation_ratio:.2f}x expected",
        ]

        if self.model_spread > abs(self.historical_var) * 0.3:
            lines.append("")
            lines.append(
                "⚠ HIGH MODEL SPREAD: VaR estimates diverge significantly. "
                "Model risk is elevated."
            )

        if self.tail_index > 0 and self.tail_index < 3:
            lines.append("")
            lines.append(
                f"⚠ HEAVY TAILS: tail index={self.tail_index:.2f} implies "
                f"infinite kurtosis. Gaussian VaR is unreliable."
            )

        lines.append("")
        lines.append(
            "NOTE: Gaussian VaR systematically underestimates financial tail risk. "
            "Student-t or Monte Carlo estimates are more appropriate."
        )

        return "\n".join(lines)

    @staticmethod
    def backtest_var(
        returns: pd.Series,
        var_series: pd.Series,
        confidence: float = 0.99,
    ) -> dict[str, float]:
        """Count VaR violations for backtesting."""
        common = returns.index.intersection(var_series.index)
        r = returns.loc[common]
        v = var_series.loc[common]

        violations = (r < v).sum()
        expected = len(r) * (1.0 - confidence)
        ratio = violations / max(expected, 1e-9)

        return {
            "violations": int(violations),
            "expected": float(expected),
            "ratio": float(ratio),
            "n_obs": len(r),
        }
