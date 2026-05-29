"""
Trading-session metadata.

Session structure governs how features should be interpreted: a 24x7 crypto
tape has no gaps and no overnight risk, whereas CME futures carry maintenance
breaks and settlement-driven discontinuities that inflate true-range and break
naive annualization. Centralizing this here lets downstream engines reason about
session structure per asset instead of assuming crypto-style continuity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class SessionInfo:
    session_id: str
    description: str
    timezone: str
    is_24x7: bool
    # Approximate regular-trading-hours window in the session timezone.
    rth_open: str | None = None
    rth_close: str | None = None
    has_overnight_gap: bool = True


SESSIONS: Dict[str, SessionInfo] = {
    "24x7": SessionInfo(
        session_id="24x7",
        description="Continuous (crypto)",
        timezone="UTC",
        is_24x7=True,
        rth_open=None,
        rth_close=None,
        has_overnight_gap=False,
    ),
    "CME": SessionInfo(
        session_id="CME",
        description="CME Globex futures",
        timezone="America/Chicago",
        is_24x7=False,
        rth_open="08:30",
        rth_close="15:00",
        has_overnight_gap=True,
    ),
    "ICE": SessionInfo(
        session_id="ICE",
        description="ICE futures (DXY)",
        timezone="America/New_York",
        is_24x7=False,
        rth_open="08:00",
        rth_close="17:00",
        has_overnight_gap=True,
    ),
}


def get_session(session_id: str) -> SessionInfo:
    return SESSIONS.get(session_id, SESSIONS["24x7"])
