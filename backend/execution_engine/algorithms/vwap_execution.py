"""
Volume-Weighted Average Price (VWAP) execution algorithm.

Distributes execution according to the historical intraday volume curve,
concentrating trading during high-volume periods to minimize market impact.

VWAP execution targets matching the market VWAP benchmark by trading
proportionally to expected volume in each time interval.

Statistical assumptions:
- Intraday volume follows a U-shaped pattern (high at open/close, low midday).
- Historical volume profile is a reasonable forecast of today's pattern.
- Market impact per dollar traded is lower during high-volume periods.

Known limitations:
- Volume profile prediction error causes deviation from VWAP target.
- Unusual trading days (news, earnings) invalidate the historical curve.
- Large orders relative to daily volume cannot achieve VWAP without impact.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from execution_engine.execution_base import (
    ChildOrder,
    ExecutionAlgorithm,
    OrderStatus,
    OrderType,
    ParentOrder,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VWAPConfig:
    n_buckets: int = 20
    max_participation_rate: float = 0.10
    min_slice_quantity: float = 1.0
    default_duration_minutes: int = 120
    volume_curve_halflife_days: int = 20
    adaptive: bool = True


@dataclass(frozen=True)
class VWAPSchedule:
    slices: list[ChildOrder]
    volume_profile: list[float]
    participation_rates: list[float]
    expected_vwap_tracking: float
    total_quantity: float
    n_buckets: int
    warnings: list[str] = field(default_factory=list)


class VWAPAlgorithm:
    """
    Generate VWAP-tracking execution schedule.

    Uses a historical volume curve to allocate child order quantities
    proportionally to expected bucket volume.
    """

    def __init__(self, config: VWAPConfig | None = None) -> None:
        self._config = config or VWAPConfig()

    def generate_schedule(
        self,
        parent: ParentOrder,
        historical_volumes: pd.DataFrame | None = None,
        start_time: pd.Timestamp | None = None,
        end_time: pd.Timestamp | None = None,
    ) -> VWAPSchedule:
        cfg = self._config
        warnings: list[str] = []

        t_start = start_time or parent.start_time or pd.Timestamp.now(tz="UTC")
        if end_time:
            t_end = end_time
        elif parent.end_time:
            t_end = parent.end_time
        else:
            t_end = t_start + pd.Timedelta(minutes=cfg.default_duration_minutes)

        duration = (t_end - t_start).total_seconds()
        bucket_duration = duration / cfg.n_buckets

        if historical_volumes is not None and not historical_volumes.empty:
            vol_profile = self._estimate_volume_curve(
                historical_volumes, cfg.n_buckets, cfg.volume_curve_halflife_days,
            )
        else:
            warnings.append("No volume data, using U-shaped default curve")
            vol_profile = self._default_volume_curve(cfg.n_buckets)

        vol_sum = sum(vol_profile)
        if vol_sum < 1e-12:
            vol_profile = [1.0 / cfg.n_buckets] * cfg.n_buckets
            vol_sum = 1.0

        vol_fractions = [v / vol_sum for v in vol_profile]

        quantities = [parent.total_quantity * f for f in vol_fractions]

        participation_rates = []
        for i, qty in enumerate(quantities):
            if vol_profile[i] > 0:
                rate = qty / vol_profile[i]
                if rate > cfg.max_participation_rate:
                    quantities[i] = vol_profile[i] * cfg.max_participation_rate
                    warnings.append(
                        f"Bucket {i}: participation capped at {cfg.max_participation_rate:.1%}"
                    )
                    rate = cfg.max_participation_rate
                participation_rates.append(rate)
            else:
                participation_rates.append(0.0)

        qty_sum = sum(quantities)
        if qty_sum > 0 and abs(qty_sum - parent.total_quantity) > 1e-6:
            scale = parent.total_quantity / qty_sum
            quantities = [q * scale for q in quantities]

        children = []
        for i in range(cfg.n_buckets):
            if quantities[i] < cfg.min_slice_quantity:
                continue

            scheduled = t_start + pd.Timedelta(seconds=bucket_duration * (i + 0.5))

            child = ChildOrder(
                parent_id=parent.order_id,
                symbol=parent.symbol,
                side=parent.side,
                order_type=OrderType.MARKET,
                quantity=quantities[i],
                scheduled_time=scheduled,
                slice_index=i,
                total_slices=cfg.n_buckets,
                status=OrderStatus.PENDING,
                metadata={
                    "algorithm": ExecutionAlgorithm.VWAP.value,
                    "volume_fraction": vol_fractions[i],
                    "participation_rate": participation_rates[i],
                },
            )
            children.append(child)

        return VWAPSchedule(
            slices=children,
            volume_profile=vol_profile,
            participation_rates=participation_rates,
            expected_vwap_tracking=self._estimate_tracking_error(vol_fractions),
            total_quantity=parent.total_quantity,
            n_buckets=cfg.n_buckets,
            warnings=warnings,
        )

    @staticmethod
    def _estimate_volume_curve(
        historical: pd.DataFrame,
        n_buckets: int,
        halflife: int,
    ) -> list[float]:
        """
        Estimate intraday volume curve from historical data.

        Expects a DataFrame with a time column and volume column,
        or intraday indexed data.
        """
        if "volume" in historical.columns:
            vol_series = historical["volume"]
        else:
            vol_series = historical.iloc[:, 0]

        n_obs = len(vol_series)
        bucket_size = max(1, n_obs // n_buckets)
        profile = []
        for i in range(n_buckets):
            start_idx = i * bucket_size
            end_idx = min(start_idx + bucket_size, n_obs)
            bucket_vol = vol_series.iloc[start_idx:end_idx]
            if len(bucket_vol) > 0:
                ewm_vol = bucket_vol.ewm(halflife=max(1, halflife), min_periods=1).mean()
                profile.append(float(ewm_vol.iloc[-1]))
            else:
                profile.append(0.0)

        return profile

    @staticmethod
    def _default_volume_curve(n_buckets: int) -> list[float]:
        """
        Generate synthetic U-shaped intraday volume curve.

        Higher volume at market open and close, lower in the middle.
        Based on empirical equity market patterns.
        """
        x = np.linspace(0, 1, n_buckets)
        curve = 1.0 + 0.8 * (np.exp(-10 * x) + np.exp(-10 * (1 - x)))
        curve /= curve.sum()
        return curve.tolist()

    @staticmethod
    def _estimate_tracking_error(vol_fractions: list[float]) -> float:
        """Estimate expected VWAP tracking error from participation profile."""
        n = len(vol_fractions)
        if n == 0:
            return 0.0
        uniform = 1.0 / n
        deviations = [(f - uniform) ** 2 for f in vol_fractions]
        return float(np.sqrt(sum(deviations) / n))
