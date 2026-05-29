"""
Portfolio diversification metrics.

Measures how well the portfolio spreads risk across assets using multiple
complementary metrics that capture different aspects of diversification.

Metrics implemented:
- Effective N (inverse HHI): how many "equivalent equal-weight" positions
- Diversification Ratio (Choueifaty): ratio of weighted-avg vol to portfolio vol
- Entropy-based diversification: information-theoretic measure
- Correlation-based diversification: average off-diagonal correlation

Statistical assumptions:
- Diversification benefits are linear in normal markets.
- Correlation breakdown in stress reduces effective diversification.
- These metrics are point-in-time snapshots — diversification stability matters.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiversificationReport:
    hhi: float
    effective_n: float
    diversification_ratio: float
    entropy: float
    max_entropy: float
    entropy_ratio: float
    avg_correlation: float
    n_positions: int
    warnings: list[str] = field(default_factory=list)


class DiversificationAnalyzer:
    """Compute diversification metrics from weights and covariance."""

    def analyze(
        self,
        weights: dict[str, float],
        covariance_matrix: pd.DataFrame | None = None,
        correlation_matrix: pd.DataFrame | None = None,
    ) -> DiversificationReport:
        warnings: list[str] = []

        w_abs = {s: abs(w) for s, w in weights.items() if abs(w) > 1e-8}
        n_pos = len(w_abs)

        if n_pos == 0:
            return DiversificationReport(
                hhi=0.0, effective_n=0.0, diversification_ratio=1.0,
                entropy=0.0, max_entropy=0.0, entropy_ratio=0.0,
                avg_correlation=0.0, n_positions=0,
                warnings=["No active positions"],
            )

        total_abs = sum(w_abs.values())
        w_norm = {s: w / total_abs for s, w in w_abs.items()} if total_abs > 0 else w_abs

        hhi = sum(w ** 2 for w in w_norm.values())
        effective_n = 1.0 / hhi if hhi > 1e-12 else 0.0

        entropy = -sum(
            w * np.log(max(w, 1e-15)) for w in w_norm.values()
        )
        max_entropy = np.log(n_pos) if n_pos > 0 else 0.0
        entropy_ratio = entropy / max_entropy if max_entropy > 0 else 0.0

        div_ratio = 1.0
        avg_corr = 0.0

        if covariance_matrix is not None:
            symbols = [s for s in w_norm if s in covariance_matrix.columns]
            if len(symbols) >= 2:
                cov = covariance_matrix.loc[symbols, symbols].values
                w_arr = np.array([w_norm[s] for s in symbols])

                vols = np.sqrt(np.diag(cov))
                weighted_avg_vol = float(w_arr @ vols)
                port_var = float(w_arr @ cov @ w_arr)
                port_vol = np.sqrt(max(port_var, 1e-15))
                div_ratio = weighted_avg_vol / port_vol if port_vol > 1e-12 else 1.0

        if correlation_matrix is not None:
            symbols = [s for s in w_norm if s in correlation_matrix.columns]
            if len(symbols) >= 2:
                corr = correlation_matrix.loc[symbols, symbols].values
                n = len(symbols)
                mask = ~np.eye(n, dtype=bool)
                avg_corr = float(corr[mask].mean())

        if effective_n < 3 and n_pos >= 5:
            warnings.append(
                f"Effective N ({effective_n:.1f}) much lower than actual positions ({n_pos}). "
                "Portfolio may be concentrated."
            )
        if avg_corr > 0.6:
            warnings.append(
                f"Average correlation {avg_corr:.3f} is high. "
                "Diversification benefit may be limited."
            )

        return DiversificationReport(
            hhi=hhi,
            effective_n=effective_n,
            diversification_ratio=div_ratio,
            entropy=entropy,
            max_entropy=max_entropy,
            entropy_ratio=entropy_ratio,
            avg_correlation=avg_corr,
            n_positions=n_pos,
            warnings=warnings,
        )
