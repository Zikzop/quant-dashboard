"""
Gross and net exposure computation — the foundation of exposure monitoring.

Gross exposure = sum of absolute position values (measures total market risk).
Net exposure = long value minus short value (measures directional bias).
Both are tracked as ratios to portfolio NAV.

Volatility-adjusted exposure weights each position by its realized volatility,
giving a risk-weighted view that better reflects actual portfolio risk than
naive dollar exposure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExposureSnapshot:
    """Point-in-time exposure metrics."""

    timestamp: pd.Timestamp
    nav: float
    gross_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    gross_leverage: float
    net_leverage: float
    vol_adjusted_gross: float
    vol_adjusted_net: float
    long_count: int
    short_count: int
    cash_weight: float


class GrossNetExposureEngine:
    """
    Computes raw and volatility-adjusted exposure metrics.

    Volatility-adjusted exposure multiplies each position's weight by its
    realized volatility relative to portfolio average volatility, giving
    higher-vol positions more risk weight.
    """

    def __init__(self) -> None:
        self._history: list[ExposureSnapshot] = []

    def compute(
        self,
        positions: dict[str, float],
        prices: dict[str, float],
        nav: float,
        timestamp: pd.Timestamp,
        volatilities: dict[str, float] | None = None,
    ) -> ExposureSnapshot:
        """
        Compute exposure snapshot.

        Parameters
        ----------
        positions : symbol -> signed quantity
        prices : symbol -> current price
        nav : portfolio net asset value
        volatilities : symbol -> annualized volatility (optional)
        """
        if nav <= 0:
            raise ValueError(f"NAV must be positive, got {nav}")

        long_exposure = 0.0
        short_exposure = 0.0
        long_count = 0
        short_count = 0
        vol_weighted_long = 0.0
        vol_weighted_short = 0.0

        avg_vol = 1.0
        if volatilities:
            vols = [v for v in volatilities.values() if v > 0]
            avg_vol = float(np.mean(vols)) if vols else 1.0

        for symbol, qty in positions.items():
            if qty == 0.0:
                continue
            price = prices.get(symbol, 0.0)
            mv = qty * price
            vol_scale = 1.0
            if volatilities and symbol in volatilities and avg_vol > 0:
                vol_scale = volatilities[symbol] / avg_vol

            if mv > 0:
                long_exposure += mv
                long_count += 1
                vol_weighted_long += mv * vol_scale
            else:
                short_exposure += abs(mv)
                short_count += 1
                vol_weighted_short += abs(mv) * vol_scale

        gross = long_exposure + short_exposure
        net = long_exposure - short_exposure
        cash = nav - net

        snap = ExposureSnapshot(
            timestamp=timestamp,
            nav=nav,
            gross_exposure=gross,
            net_exposure=net,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            gross_leverage=gross / nav,
            net_leverage=net / nav,
            vol_adjusted_gross=(vol_weighted_long + vol_weighted_short) / nav,
            vol_adjusted_net=(vol_weighted_long - vol_weighted_short) / nav,
            long_count=long_count,
            short_count=short_count,
            cash_weight=cash / nav,
        )
        self._history.append(snap)
        return snap

    def history(self) -> list[ExposureSnapshot]:
        return list(self._history)

    def to_dataframe(self) -> pd.DataFrame:
        if not self._history:
            return pd.DataFrame()
        records = []
        for s in self._history:
            records.append({
                "timestamp": s.timestamp,
                "gross_leverage": s.gross_leverage,
                "net_leverage": s.net_leverage,
                "vol_adj_gross": s.vol_adjusted_gross,
                "vol_adj_net": s.vol_adjusted_net,
                "long_count": s.long_count,
                "short_count": s.short_count,
                "cash_weight": s.cash_weight,
            })
        return pd.DataFrame(records).set_index("timestamp")
