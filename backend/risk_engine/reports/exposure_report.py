"""
Exposure report — detailed exposure breakdown and concentration analysis.

Provides the full exposure decomposition for risk committee review:
- Directional exposure (long/short)
- Volatility-adjusted exposure
- Sector/factor concentration
- Position-level detail
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExposureReport:
    """Detailed exposure diagnostic report."""

    gross_leverage: float = 0.0
    net_leverage: float = 0.0
    long_exposure: float = 0.0
    short_exposure: float = 0.0
    vol_adjusted_gross: float = 0.0
    n_positions: int = 0
    long_count: int = 0
    short_count: int = 0
    hhi: float = 0.0
    effective_n: float = 0.0
    max_position_weight: float = 0.0
    max_position_symbol: str = ""
    top_5_weight: float = 0.0
    sector_weights: dict[str, float] = field(default_factory=dict)
    max_sector_weight: float = 0.0
    max_sector_name: str = ""
    market_beta: float = 0.0
    cash_weight: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def summary_text(self) -> str:
        lines = [
            "=== EXPOSURE REPORT ===",
            "",
            "--- LEVERAGE ---",
            f"  Gross:           {self.gross_leverage:.2f}x",
            f"  Net:             {self.net_leverage:+.2f}x",
            f"  Vol-Adjusted:    {self.vol_adjusted_gross:.2f}x",
            f"  Cash Weight:     {self.cash_weight:.2%}",
            "",
            "--- POSITIONS ---",
            f"  Total:           {self.n_positions}",
            f"  Long:            {self.long_count}",
            f"  Short:           {self.short_count}",
            f"  Effective N:     {self.effective_n:.1f}",
            "",
            "--- CONCENTRATION ---",
            f"  HHI:             {self.hhi:.4f}",
            f"  Max Position:    {self.max_position_symbol} ({self.max_position_weight:.2%})",
            f"  Top 5 Weight:    {self.top_5_weight:.2%}",
        ]

        if self.sector_weights:
            lines.append("")
            lines.append("--- SECTOR EXPOSURE ---")
            for sector, w in sorted(
                self.sector_weights.items(), key=lambda x: -x[1]
            ):
                lines.append(f"  {sector:25s} {w:.2%}")

        if self.market_beta != 0.0:
            lines.append("")
            lines.append(f"  Market Beta:     {self.market_beta:.2f}")

        if self.warnings:
            lines.append("")
            lines.append("--- WARNINGS ---")
            for w in self.warnings:
                lines.append(f"  • {w}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gross_leverage": self.gross_leverage,
            "net_leverage": self.net_leverage,
            "vol_adjusted_gross": self.vol_adjusted_gross,
            "n_positions": self.n_positions,
            "hhi": self.hhi,
            "effective_n": self.effective_n,
            "max_position": self.max_position_symbol,
            "max_weight": self.max_position_weight,
            "market_beta": self.market_beta,
            "sector_weights": self.sector_weights,
        }
