"""
Portfolio exposure decomposition — factor, sector, and directional analysis.

Decomposes portfolio exposure into interpretable components for risk monitoring
and regulatory reporting.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExposureDecomposition:
    gross_exposure: float
    net_exposure: float
    long_exposure: float
    short_exposure: float
    gross_leverage: float
    net_leverage: float
    sector_exposures: dict[str, float]
    top_positions: list[tuple[str, float]]
    direction_bias: str
    warnings: list[str] = field(default_factory=list)


class PortfolioExposureAnalyzer:
    """Decompose portfolio weights into exposure categories."""

    def analyze(
        self,
        weights: dict[str, float],
        sector_map: dict[str, str] | None = None,
        nav: float = 1.0,
        top_n: int = 5,
    ) -> ExposureDecomposition:
        warnings: list[str] = []

        long_exp = sum(w for w in weights.values() if w > 0)
        short_exp = sum(abs(w) for w in weights.values() if w < 0)
        gross = long_exp + short_exp
        net = long_exp - short_exp

        gross_lev = gross
        net_lev = net

        sector_exp: dict[str, float] = {}
        if sector_map:
            for symbol, w in weights.items():
                sec = sector_map.get(symbol, "unknown")
                sector_exp[sec] = sector_exp.get(sec, 0.0) + w

        sorted_positions = sorted(
            weights.items(), key=lambda x: abs(x[1]), reverse=True
        )
        top = sorted_positions[:top_n]

        if gross > 0:
            net_ratio = abs(net) / gross
            if net_ratio > 0.8:
                bias = "strongly_directional"
            elif net_ratio > 0.5:
                bias = "directional"
            elif net_ratio > 0.2:
                bias = "moderate_directional"
            else:
                bias = "market_neutral"
        else:
            bias = "flat"

        if gross > 2.0:
            warnings.append(f"High gross leverage: {gross:.3f}")
        if any(abs(w) > 0.20 for w in weights.values()):
            concentrated = [s for s, w in weights.items() if abs(w) > 0.20]
            warnings.append(f"Concentrated positions: {concentrated}")

        return ExposureDecomposition(
            gross_exposure=gross,
            net_exposure=net,
            long_exposure=long_exp,
            short_exposure=short_exp,
            gross_leverage=gross_lev,
            net_leverage=net_lev,
            sector_exposures=sector_exp,
            top_positions=top,
            direction_bias=bias,
            warnings=warnings,
        )
