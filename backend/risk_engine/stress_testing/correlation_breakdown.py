"""
Correlation breakdown stress — testing portfolio under correlated sell-offs.

The most dangerous lie in portfolio construction is "diversification."
In normal markets, assets have moderate correlations and diversification
works. In crises, correlations surge toward 1.0 and every position
moves against you simultaneously.

This module estimates portfolio losses under correlation breakdown
scenarios where diversification benefits partially or fully disappear.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CorrelationBreakdownResult:
    """Impact of correlation breakdown on portfolio risk."""

    normal_portfolio_vol: float
    stressed_portfolio_vol: float
    vol_increase_pct: float
    diversification_ratio_normal: float
    diversification_ratio_stressed: float
    implied_loss_1d: float
    implied_loss_5d: float
    implied_loss_20d: float
    worst_case_correlation: float


class CorrelationBreakdownEngine:
    """
    Estimates portfolio risk under correlation stress scenarios.

    Tests three levels:
    1. Moderate: correlations increase by 50% toward 1.0
    2. Severe: correlations increase by 80% toward 1.0
    3. Total: all correlations → 1.0 (worst case, no diversification)
    """

    def __init__(self) -> None:
        pass

    def analyze(
        self,
        position_weights: dict[str, float],
        position_vols: dict[str, float],
        correlation_matrix: np.ndarray | None = None,
        gross_leverage: float = 1.0,
    ) -> dict[str, CorrelationBreakdownResult]:
        symbols = sorted(position_weights.keys())
        n = len(symbols)

        if n == 0:
            return {}

        w = np.array([position_weights[s] for s in symbols])
        v = np.array([position_vols.get(s, 0.15) for s in symbols])

        if correlation_matrix is not None and correlation_matrix.shape == (n, n):
            corr = correlation_matrix
        else:
            corr = np.eye(n) * 0.5 + 0.5 * np.ones((n, n))
            np.fill_diagonal(corr, 1.0)

        cov = np.outer(v, v) * corr
        normal_var = float(w @ cov @ w)
        normal_vol = np.sqrt(max(normal_var, 0.0))

        results = {}
        for label, shift in [("moderate", 0.5), ("severe", 0.8), ("total", 1.0)]:
            stressed_corr = corr + shift * (np.ones_like(corr) - corr)
            np.fill_diagonal(stressed_corr, 1.0)
            stressed_cov = np.outer(v, v) * stressed_corr
            stressed_var = float(w @ stressed_cov @ w)
            stressed_vol = np.sqrt(max(stressed_var, 0.0))

            sum_wv = float(np.sum(np.abs(w) * v))
            div_normal = sum_wv / max(normal_vol, 1e-9)
            div_stressed = sum_wv / max(stressed_vol, 1e-9)

            vol_increase = (stressed_vol - normal_vol) / max(normal_vol, 1e-9)

            ann_stressed = stressed_vol * np.sqrt(252)
            daily = ann_stressed / np.sqrt(252) * gross_leverage

            results[label] = CorrelationBreakdownResult(
                normal_portfolio_vol=float(normal_vol * np.sqrt(252)),
                stressed_portfolio_vol=float(ann_stressed),
                vol_increase_pct=float(vol_increase),
                diversification_ratio_normal=float(div_normal),
                diversification_ratio_stressed=float(div_stressed),
                implied_loss_1d=float(-2.33 * daily),
                implied_loss_5d=float(-2.33 * daily * np.sqrt(5)),
                implied_loss_20d=float(-2.33 * daily * np.sqrt(20)),
                worst_case_correlation=float(shift),
            )

        return results
