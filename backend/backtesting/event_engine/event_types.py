"""Canonical event type enumeration with strict causal ordering."""

from __future__ import annotations

from enum import IntEnum, unique


@unique
class EventType(IntEnum):
    """
    Event types ordered by causal priority.

    Lower value = higher priority = processed first within the same timestamp.
    This prevents look-ahead: market data must arrive before signals,
    signals before orders, orders before fills.
    """

    MARKET = 0
    SIGNAL = 10
    ORDER = 20
    FILL = 30
    PORTFOLIO_UPDATE = 40
    RISK_UPDATE = 50
