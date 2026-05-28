"""
Timeframe specifications (data-acquisition config).

This is the single source of truth for the six supported timeframes, replacing
the ``TF_CONFIG`` dict that previously lived inline in ``main.py``. It maps the
platform's canonical timeframe labels to:

* the provider-native interval + lookback period (yfinance vocabulary today;
  a different provider maps the same canonical label to its own vocabulary),
* the optional resample rule (4H is synthesized from 1h bars),
* ``bars_per_year`` for correct volatility annualization per timeframe,
* the number of bars to render on the chart.

Engines never see this — they consume normalized OHLCV. Only the data-access
layer reads these specs to translate a canonical request into provider params.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

CANONICAL_TIMEFRAMES = ("1m", "5m", "15m", "1H", "4H", "1D")


@dataclass(frozen=True)
class TimeframeSpec:
    timeframe: str
    yf_interval: str
    yf_period: str
    chart_bars: int
    bars_per_year: int
    resample: str | None = None

    @property
    def is_intraday(self) -> bool:
        return self.timeframe != "1D"


TIMEFRAME_SPECS: Dict[str, TimeframeSpec] = {
    "1m": TimeframeSpec("1m", "1m", "7d", 300, 525_960),
    "5m": TimeframeSpec("5m", "5m", "60d", 200, 105_192),
    "15m": TimeframeSpec("15m", "15m", "60d", 150, 35_064),
    "1H": TimeframeSpec("1H", "1h", "730d", 120, 8_766),
    "4H": TimeframeSpec("4H", "1h", "730d", 120, 2_190, resample="4h"),
    "1D": TimeframeSpec("1D", "1d", "2y", 120, 365),
}

VALID_TIMEFRAMES = set(TIMEFRAME_SPECS.keys())


def get_timeframe_spec(timeframe: str) -> TimeframeSpec:
    spec = TIMEFRAME_SPECS.get(timeframe)
    if spec is None:
        valid = ", ".join(sorted(VALID_TIMEFRAMES))
        raise ValueError(f"Invalid timeframe '{timeframe}'. Valid: {valid}")
    return spec
