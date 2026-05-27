"""
Portfolio concentration risk analysis.

Measures concentration across multiple dimensions:
- Single-name concentration
- Sector concentration
- Factor concentration
- Tail concentration (risk contribution)

Concentration is a leading indicator of drawdown severity — concentrated
portfolios have higher maximum drawdown for the same expected vol.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConcentrationReport:
    hhi: float
    top_1_weight: float
    top_3_weight: float
    top_5_weight: float
    gini_coefficient: float
    effective_n: float
    sector_hhi: float
    max_sector_weight: float
    risk_concentration_hhi: float
    concentration_regime: str
    warnings: list[str] = field(default_factory=list)


class ConcentrationAnalyzer:
    """
    Multi-dimensional concentration risk assessment.

    Combines weight-based, sector-based, and risk-contribution-based
    concentration metrics into a unified report.
    """

    def __init__(
        self,
        hhi_warning: float = 0.15,
        hhi_critical: float = 0.25,
    ) -> None:
        self._hhi_warning = hhi_warning
        self._hhi_critical = hhi_critical

    def analyze(
        self,
        weights: dict[str, float],
        sector_map: dict[str, str] | None = None,
        risk_contributions: dict[str, float] | None = None,
    ) -> ConcentrationReport:
        warnings: list[str] = []

        abs_weights = sorted(
            [abs(w) for w in weights.values() if abs(w) > 1e-8],
            reverse=True,
        )
        n = len(abs_weights)

        if n == 0:
            return ConcentrationReport(
                hhi=0.0, top_1_weight=0.0, top_3_weight=0.0, top_5_weight=0.0,
                gini_coefficient=0.0, effective_n=0.0, sector_hhi=0.0,
                max_sector_weight=0.0, risk_concentration_hhi=0.0,
                concentration_regime="flat",
                warnings=["No active positions"],
            )

        total_abs = sum(abs_weights)
        if total_abs < 1e-12:
            norm_w = abs_weights
        else:
            norm_w = [w / total_abs for w in abs_weights]

        hhi = sum(w ** 2 for w in norm_w)
        effective_n = 1.0 / hhi if hhi > 1e-12 else 0.0
        top_1 = norm_w[0] if n >= 1 else 0.0
        top_3 = sum(norm_w[:3]) if n >= 3 else sum(norm_w)
        top_5 = sum(norm_w[:5]) if n >= 5 else sum(norm_w)

        gini = self._gini(norm_w)

        sector_hhi = 0.0
        max_sector = 0.0
        if sector_map:
            sector_w: dict[str, float] = {}
            for symbol, w in weights.items():
                sec = sector_map.get(symbol, "unknown")
                sector_w[sec] = sector_w.get(sec, 0.0) + abs(w)
            if total_abs > 1e-12:
                sec_norm = {s: w / total_abs for s, w in sector_w.items()}
            else:
                sec_norm = sector_w
            sector_hhi = sum(w ** 2 for w in sec_norm.values())
            max_sector = max(sec_norm.values()) if sec_norm else 0.0

        rc_hhi = 0.0
        if risk_contributions:
            rc_vals = [abs(v) for v in risk_contributions.values() if abs(v) > 1e-8]
            rc_total = sum(rc_vals)
            if rc_total > 1e-12:
                rc_norm = [v / rc_total for v in rc_vals]
                rc_hhi = sum(v ** 2 for v in rc_norm)

        if hhi >= self._hhi_critical:
            regime = "critical"
            warnings.append(f"HHI {hhi:.4f} exceeds critical threshold {self._hhi_critical}")
        elif hhi >= self._hhi_warning:
            regime = "elevated"
            warnings.append(f"HHI {hhi:.4f} exceeds warning threshold {self._hhi_warning}")
        else:
            regime = "normal"

        if top_1 > 0.30:
            warnings.append(f"Top position accounts for {top_1:.1%} of exposure")

        return ConcentrationReport(
            hhi=hhi,
            top_1_weight=top_1,
            top_3_weight=top_3,
            top_5_weight=top_5,
            gini_coefficient=gini,
            effective_n=effective_n,
            sector_hhi=sector_hhi,
            max_sector_weight=max_sector,
            risk_concentration_hhi=rc_hhi,
            concentration_regime=regime,
            warnings=warnings,
        )

    @staticmethod
    def _gini(values: list[float]) -> float:
        """Gini coefficient for weight inequality. 0 = equal, 1 = concentrated."""
        n = len(values)
        if n <= 1:
            return 0.0
        sorted_v = sorted(values)
        cum = np.cumsum(sorted_v)
        total = cum[-1]
        if total < 1e-12:
            return 0.0
        index = np.arange(1, n + 1)
        return float((2 * np.sum(index * sorted_v) / (n * total)) - (n + 1) / n)
