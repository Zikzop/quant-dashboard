"""
Factor exposure estimation — market beta, size, momentum, and volatility factors.

Hidden factor exposure is one of the most dangerous risks in a systematic
portfolio. A portfolio can appear diversified across names but be heavily
concentrated in a single factor (e.g., long momentum everywhere). Factor
exposure analysis reveals these hidden correlations.

NOTE: This module provides simplified factor estimation from returns.
A production system would integrate with a commercial factor model
(Barra, Axioma, or similar).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FactorExposureSnapshot:
    """Point-in-time factor exposure estimates."""

    market_beta: float
    size_exposure: float
    momentum_exposure: float
    volatility_exposure: float
    residual_risk: float
    r_squared: float
    factor_contributions: dict[str, float]


class FactorExposureEngine:
    """
    Estimates portfolio factor exposures via returns-based regression.

    Uses trailing returns to regress portfolio returns against factor
    proxies. This captures realized factor tilts even when they're
    unintentional.

    LIMITATION: Returns-based analysis is backward-looking and suffers
    from multicollinearity between factors. Holdings-based factor
    analysis (via Barra/Axioma) is more precise but requires external data.
    """

    def __init__(self, lookback_days: int = 60) -> None:
        self._lookback = lookback_days

    def estimate(
        self,
        portfolio_returns: pd.Series,
        market_returns: pd.Series,
        factor_returns: dict[str, pd.Series] | None = None,
    ) -> FactorExposureSnapshot:
        """
        Estimate factor exposures from trailing returns.

        Parameters
        ----------
        portfolio_returns : daily portfolio returns
        market_returns : daily market benchmark returns
        factor_returns : optional dict of factor name -> daily returns
        """
        common_idx = portfolio_returns.index.intersection(market_returns.index)
        if len(common_idx) < 20:
            return self._empty_snapshot()

        common_idx = common_idx[-self._lookback:]
        port_r = portfolio_returns.loc[common_idx].values
        mkt_r = market_returns.loc[common_idx].values

        factors = {"market": mkt_r}
        if factor_returns:
            for fname, fseries in factor_returns.items():
                f_common = fseries.reindex(common_idx).dropna()
                if len(f_common) == len(common_idx):
                    factors[fname] = f_common.values

        X = np.column_stack(list(factors.values()))
        X = np.column_stack([np.ones(len(X)), X])
        y = port_r

        try:
            betas, residuals, _, _ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            return self._empty_snapshot()

        ss_res = np.sum((y - X @ betas) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1.0 - ss_res / max(ss_tot, 1e-12)

        factor_names = list(factors.keys())
        contributions = {}
        for i, name in enumerate(factor_names):
            contributions[name] = float(betas[i + 1])

        market_beta = contributions.get("market", 0.0)
        residual_var = ss_res / max(len(y) - len(betas), 1)
        residual_risk = float(np.sqrt(residual_var) * np.sqrt(252))

        return FactorExposureSnapshot(
            market_beta=market_beta,
            size_exposure=contributions.get("size", 0.0),
            momentum_exposure=contributions.get("momentum", 0.0),
            volatility_exposure=contributions.get("volatility", 0.0),
            residual_risk=residual_risk,
            r_squared=max(0.0, r_squared),
            factor_contributions=contributions,
        )

    @staticmethod
    def _empty_snapshot() -> FactorExposureSnapshot:
        return FactorExposureSnapshot(
            market_beta=0.0,
            size_exposure=0.0,
            momentum_exposure=0.0,
            volatility_exposure=0.0,
            residual_risk=0.0,
            r_squared=0.0,
            factor_contributions={},
        )
