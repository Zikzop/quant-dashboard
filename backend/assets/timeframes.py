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

HISTORICAL_RANGES = ("1D", "1W", "1M", "3M", "6M", "1Y", "2Y")
DEFAULT_HISTORICAL_RANGE = "3M"
VALID_HISTORICAL_RANGES = set(HISTORICAL_RANGES)

RANGE_DAYS: Dict[str, int] = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "2Y": 730,
}

# Approximate bars per calendar day per canonical timeframe (for chart window sizing).
BARS_PER_DAY: Dict[str, int] = {
    "1m": 390,
    "5m": 78,
    "15m": 26,
    "1H": 24,
    "4H": 6,
    "1D": 1,
}

# Hard caps to keep API payloads bounded on very long intraday windows.
MAX_DISPLAY_BARS: Dict[str, int] = {
    "1m": 2_000,
    "5m": 4_000,
    "15m": 6_000,
    "1H": 12_000,
    "4H": 4_000,
    "1D": 600,
}


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


# TIMEFRAME_CONFIG — canonical acquisition + display defaults.
# ``chart_bars`` is the fallback when no range is supplied; use
# ``chart_bars_for_range`` for institutional lookback windows.
TIMEFRAME_SPECS: Dict[str, TimeframeSpec] = {
    "1m": TimeframeSpec("1m", "1m", "7d", 390, 525_960),
    "5m": TimeframeSpec("5m", "5m", "60d", 390, 105_192),
    "15m": TimeframeSpec("15m", "15m", "60d", 390, 35_064),
    "1H": TimeframeSpec("1H", "1h", "730d", 720, 8_766),
    "4H": TimeframeSpec("4H", "1h", "730d", 360, 2_190, resample="4h"),
    "1D": TimeframeSpec("1D", "1d", "2y", 504, 365),
}

VALID_TIMEFRAMES = set(TIMEFRAME_SPECS.keys())


def get_timeframe_spec(timeframe: str) -> TimeframeSpec:
    spec = TIMEFRAME_SPECS.get(timeframe)
    if spec is None:
        valid = ", ".join(sorted(VALID_TIMEFRAMES))
        raise ValueError(f"Invalid timeframe '{timeframe}'. Valid: {valid}")
    return spec


def normalize_range(range_label: str | None) -> str:
    if not range_label:
        return DEFAULT_HISTORICAL_RANGE
    upper = range_label.strip().upper()
    if upper not in VALID_HISTORICAL_RANGES:
        valid = ", ".join(sorted(VALID_HISTORICAL_RANGES))
        raise ValueError(f"Invalid range '{range_label}'. Valid: {valid}")
    return upper


def chart_bars_for_range(timeframe: str, range_label: str | None) -> int:
    """Bars to render for asset+timeframe+range (capped for payload size)."""
    spec = get_timeframe_spec(timeframe)
    rng = normalize_range(range_label)
    days = RANGE_DAYS[rng]
    bpd = BARS_PER_DAY.get(timeframe, 1)
    target = max(spec.chart_bars // 4, int(days * bpd))
    cap = MAX_DISPLAY_BARS.get(timeframe, spec.chart_bars)
    return min(max(target, 30), cap)
