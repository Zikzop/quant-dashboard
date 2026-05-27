"""
Execution clock — manages execution time tracking and market session awareness.

Provides a unified time source for the execution engine, supporting
both real-time and simulation modes. Tracks market sessions, pre/post
market periods, and trading halts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, unique

import pandas as pd

logger = logging.getLogger(__name__)


@unique
class MarketSession(Enum):
    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    POST_MARKET = "post_market"
    CLOSED = "closed"


@dataclass(frozen=True)
class TradingCalendar:
    market_open_hour: int = 9
    market_open_minute: int = 30
    market_close_hour: int = 16
    market_close_minute: int = 0
    pre_market_open_hour: int = 4
    post_market_close_hour: int = 20
    timezone: str = "America/New_York"
    trading_days: tuple[int, ...] = (0, 1, 2, 3, 4)


class ExecutionClock:
    """
    Execution time management for both simulation and live modes.
    """

    def __init__(
        self,
        calendar: TradingCalendar | None = None,
        simulation_mode: bool = True,
    ) -> None:
        self._calendar = calendar or TradingCalendar()
        self._simulation_mode = simulation_mode
        self._simulated_time: pd.Timestamp | None = None

    @property
    def now(self) -> pd.Timestamp:
        if self._simulation_mode and self._simulated_time is not None:
            return self._simulated_time
        return pd.Timestamp.now(tz="UTC")

    def advance_to(self, timestamp: pd.Timestamp) -> None:
        if not self._simulation_mode:
            raise RuntimeError("Cannot advance clock in live mode")
        if self._simulated_time is not None and timestamp < self._simulated_time:
            raise ValueError(
                f"Cannot go backwards: {timestamp} < {self._simulated_time}"
            )
        self._simulated_time = timestamp

    def get_session(self, timestamp: pd.Timestamp | None = None) -> MarketSession:
        ts = timestamp or self.now
        cal = self._calendar

        if ts.weekday() not in cal.trading_days:
            return MarketSession.CLOSED

        try:
            local = ts.tz_convert(cal.timezone)
        except Exception:
            local = ts

        hour_min = local.hour * 60 + local.minute

        open_min = cal.market_open_hour * 60 + cal.market_open_minute
        close_min = cal.market_close_hour * 60 + cal.market_close_minute
        pre_open_min = cal.pre_market_open_hour * 60
        post_close_min = cal.post_market_close_hour * 60

        if open_min <= hour_min < close_min:
            return MarketSession.REGULAR
        elif pre_open_min <= hour_min < open_min:
            return MarketSession.PRE_MARKET
        elif close_min <= hour_min < post_close_min:
            return MarketSession.POST_MARKET
        else:
            return MarketSession.CLOSED

    def is_trading_time(self, timestamp: pd.Timestamp | None = None) -> bool:
        session = self.get_session(timestamp)
        return session == MarketSession.REGULAR

    def next_market_open(self, after: pd.Timestamp | None = None) -> pd.Timestamp:
        ts = after or self.now
        cal = self._calendar

        candidate = ts.normalize() + pd.Timedelta(
            hours=cal.market_open_hour, minutes=cal.market_open_minute
        )
        if candidate <= ts:
            candidate += pd.Timedelta(days=1)

        while candidate.weekday() not in cal.trading_days:
            candidate += pd.Timedelta(days=1)

        return candidate

    def time_to_close(self, timestamp: pd.Timestamp | None = None) -> float:
        """Seconds until market close. Returns 0 if market is closed."""
        ts = timestamp or self.now
        if not self.is_trading_time(ts):
            return 0.0
        cal = self._calendar
        close = ts.normalize() + pd.Timedelta(
            hours=cal.market_close_hour, minutes=cal.market_close_minute
        )
        return max(0.0, (close - ts).total_seconds())
