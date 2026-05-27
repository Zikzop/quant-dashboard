"""
Priority event queue with causal ordering guarantee.

Within the same timestamp, events are processed in causal order:
Market -> Signal -> Order -> Fill -> PortfolioUpdate -> RiskUpdate
"""

from __future__ import annotations

import heapq
import logging
from collections import defaultdict
from typing import Iterator

from backtesting.event_engine.events import Event

logger = logging.getLogger(__name__)


class EventQueue:
    """
    Min-heap event queue preserving causal ordering.

    Events at the same timestamp are ordered by EventType priority (IntEnum value).
    Ties within the same type are broken by insertion order (FIFO).
    """

    def __init__(self) -> None:
        self._heap: list[tuple[Event, int]] = []
        self._counter: int = 0
        self._event_counts: dict[str, int] = defaultdict(int)

    def push(self, event: Event) -> None:
        heapq.heappush(self._heap, (event, self._counter))
        self._counter += 1
        self._event_counts[event.event_type.name] += 1

    def pop(self) -> Event:
        if not self._heap:
            raise IndexError("pop from empty EventQueue")
        event, _ = heapq.heappop(self._heap)
        return event

    def peek(self) -> Event | None:
        if not self._heap:
            return None
        return self._heap[0][0]

    @property
    def empty(self) -> bool:
        return len(self._heap) == 0

    def __len__(self) -> int:
        return len(self._heap)

    def drain(self) -> Iterator[Event]:
        """Yield all events in causal order."""
        while not self.empty:
            yield self.pop()

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._event_counts)

    def clear(self) -> None:
        self._heap.clear()
        self._counter = 0
        self._event_counts.clear()
