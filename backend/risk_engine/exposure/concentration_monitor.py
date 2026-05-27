"""
Concentration monitoring — single-name, sector, and HHI analysis.

A concentrated portfolio is a fragile portfolio. Concentration risk is
not just about position count — it's about the effective number of
independent bets. HHI measures this; sector overlap amplifies it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from risk_engine.risk_config import ExposureConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConcentrationSnapshot:
    """Point-in-time concentration metrics."""

    n_positions: int
    effective_n: float
    hhi: float
    max_single_name: float
    max_single_name_symbol: str
    top5_weight: float
    sector_weights: dict[str, float]
    max_sector_weight: float
    max_sector_name: str


class ConcentrationMonitor:
    """
    Monitors portfolio concentration at position and sector level.

    Effective N = 1/HHI gives the equivalent number of equal-weight positions.
    A 10-name portfolio where one stock is 50% has effective N ≈ 3.
    """

    def __init__(self, config: ExposureConfig | None = None) -> None:
        self._config = config or ExposureConfig()

    def compute(
        self,
        positions: dict[str, float],
        prices: dict[str, float],
        nav: float,
        sector_map: dict[str, str] | None = None,
    ) -> ConcentrationSnapshot:
        if nav <= 0:
            return self._empty_snapshot()

        weights: dict[str, float] = {}
        for symbol, qty in positions.items():
            if qty == 0.0:
                continue
            price = prices.get(symbol, 0.0)
            weights[symbol] = abs(qty * price) / nav

        if not weights:
            return self._empty_snapshot()

        sorted_w = sorted(weights.values(), reverse=True)
        hhi = sum(w ** 2 for w in sorted_w)
        effective_n = 1.0 / hhi if hhi > 0 else 0.0
        max_name = max(weights, key=weights.get)
        top5 = sum(sorted_w[:5])

        sector_weights: dict[str, float] = {}
        if sector_map:
            for symbol, w in weights.items():
                sector = sector_map.get(symbol, "Unknown")
                sector_weights[sector] = sector_weights.get(sector, 0.0) + w

        max_sector = max(sector_weights, key=sector_weights.get) if sector_weights else "N/A"
        max_sector_w = sector_weights.get(max_sector, 0.0)

        return ConcentrationSnapshot(
            n_positions=len(weights),
            effective_n=effective_n,
            hhi=hhi,
            max_single_name=weights[max_name],
            max_single_name_symbol=max_name,
            top5_weight=top5,
            sector_weights=sector_weights,
            max_sector_weight=max_sector_w,
            max_sector_name=max_sector,
        )

    @staticmethod
    def _empty_snapshot() -> ConcentrationSnapshot:
        return ConcentrationSnapshot(
            n_positions=0,
            effective_n=0.0,
            hhi=0.0,
            max_single_name=0.0,
            max_single_name_symbol="",
            top5_weight=0.0,
            sector_weights={},
            max_sector_weight=0.0,
            max_sector_name="N/A",
        )
