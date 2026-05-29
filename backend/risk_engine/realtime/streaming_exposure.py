"""
Streaming exposure — lightweight exposure computation for high-frequency updates.

This module provides a simplified exposure computation path optimized
for streaming updates. Unlike the full ExposureMonitor, it avoids
expensive operations (factor regression, sector analysis) and focuses
on the core metrics needed for real-time monitoring.

Future integration points:
- Kafka consumer for live position updates
- WebSocket publisher for dashboard exposure feed
- Redis cache for latest exposure state
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamingExposureUpdate:
    """Lightweight exposure update for streaming."""

    timestamp: pd.Timestamp
    gross_leverage: float
    net_leverage: float
    long_count: int
    short_count: int
    max_weight: float
    cash_pct: float


class StreamingExposureEngine:
    """
    Computes exposure metrics from position/price updates with minimal overhead.

    Designed for call frequency of 1Hz to 10Hz in a live trading context.
    All computations are O(n) in position count with no matrix operations.
    """

    def __init__(self) -> None:
        self._latest: StreamingExposureUpdate | None = None

    def update(
        self,
        positions: dict[str, float],
        prices: dict[str, float],
        cash: float,
        timestamp: pd.Timestamp,
    ) -> StreamingExposureUpdate:
        long_val = 0.0
        short_val = 0.0
        long_count = 0
        short_count = 0
        max_abs_mv = 0.0

        for symbol, qty in positions.items():
            if qty == 0.0:
                continue
            price = prices.get(symbol, 0.0)
            mv = qty * price
            abs_mv = abs(mv)
            max_abs_mv = max(max_abs_mv, abs_mv)

            if mv > 0:
                long_val += mv
                long_count += 1
            else:
                short_val += abs_mv
                short_count += 1

        nav = long_val - short_val + cash
        if nav <= 0:
            nav = 1e-9

        gross = long_val + short_val

        result = StreamingExposureUpdate(
            timestamp=timestamp,
            gross_leverage=gross / nav,
            net_leverage=(long_val - short_val) / nav,
            long_count=long_count,
            short_count=short_count,
            max_weight=max_abs_mv / nav,
            cash_pct=cash / nav,
        )
        self._latest = result
        return result

    @property
    def latest(self) -> StreamingExposureUpdate | None:
        return self._latest

    def to_dict(self) -> dict[str, Any]:
        if self._latest is None:
            return {}
        s = self._latest
        return {
            "timestamp": s.timestamp.isoformat(),
            "gross_leverage": s.gross_leverage,
            "net_leverage": s.net_leverage,
            "long_count": s.long_count,
            "short_count": s.short_count,
            "max_weight": s.max_weight,
            "cash_pct": s.cash_pct,
        }
