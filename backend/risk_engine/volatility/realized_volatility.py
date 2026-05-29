"""
Realized volatility estimation — multiple estimators for robustness.

Simple close-to-close volatility underestimates true volatility in
trending markets and overestimates it in choppy markets. We provide
exponentially-weighted, Yang-Zhang, and Parkinson estimators for
more robust risk estimation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VolatilityEstimate:
    """Multi-estimator volatility snapshot."""

    close_to_close: float
    ewma: float
    parkinson: float
    yang_zhang: float
    composite: float
    annualized_composite: float
    n_observations: int


class RealizedVolatilityEngine:
    """
    Computes realized volatility using multiple estimators.

    The composite estimate blends close-to-close, EWMA, and range-based
    estimators, reducing sensitivity to any single estimation methodology.
    """

    def __init__(
        self,
        lookback_days: int = 60,
        ewm_halflife: int = 20,
        trading_days_per_year: int = 252,
    ) -> None:
        self._lookback = lookback_days
        self._halflife = ewm_halflife
        self._ann_factor = np.sqrt(trading_days_per_year)

    def estimate_from_returns(self, returns: pd.Series) -> VolatilityEstimate:
        """Estimate volatility from return series (close-to-close only)."""
        r = returns.dropna().iloc[-self._lookback:]
        if len(r) < 10:
            return self._empty_estimate(len(r))

        cc = float(r.std())
        ewma = float(r.ewm(halflife=self._halflife).std().iloc[-1])
        composite = (cc + ewma) / 2.0

        return VolatilityEstimate(
            close_to_close=cc,
            ewma=ewma,
            parkinson=cc,
            yang_zhang=cc,
            composite=composite,
            annualized_composite=composite * self._ann_factor,
            n_observations=len(r),
        )

    def estimate_from_ohlc(self, ohlc: pd.DataFrame) -> VolatilityEstimate:
        """
        Full multi-estimator volatility from OHLC data.

        Parkinson uses high-low range; Yang-Zhang combines overnight
        and intraday components for drift-independent estimation.
        """
        df = ohlc.iloc[-self._lookback:].copy()
        n = len(df)
        if n < 10:
            return self._empty_estimate(n)

        log_ret = np.log(df["close"] / df["close"].shift(1)).dropna()
        cc = float(log_ret.std())
        ewma = float(log_ret.ewm(halflife=self._halflife).std().iloc[-1])

        log_hl = np.log(df["high"] / df["low"])
        parkinson = float(np.sqrt((1.0 / (4.0 * n * np.log(2))) * (log_hl ** 2).sum()))

        log_co = np.log(df["close"] / df["open"])
        log_oc = np.log(df["open"] / df["close"].shift(1)).dropna()

        if len(log_oc) < 5:
            yang_zhang = cc
        else:
            sigma_oc = float(log_oc.var())
            sigma_co = float(log_co.iloc[1:].var())
            k = 0.34 / (1.34 + (n + 1) / (n - 1))
            yang_zhang = float(np.sqrt(sigma_oc + k * sigma_co + (1 - k) * parkinson ** 2))

        composite = float(np.mean([cc, ewma, parkinson, yang_zhang]))

        return VolatilityEstimate(
            close_to_close=cc,
            ewma=ewma,
            parkinson=parkinson,
            yang_zhang=yang_zhang,
            composite=composite,
            annualized_composite=composite * self._ann_factor,
            n_observations=n,
        )

    def _empty_estimate(self, n: int) -> VolatilityEstimate:
        return VolatilityEstimate(
            close_to_close=0.0,
            ewma=0.0,
            parkinson=0.0,
            yang_zhang=0.0,
            composite=0.0,
            annualized_composite=0.0,
            n_observations=n,
        )
