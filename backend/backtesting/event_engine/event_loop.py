"""
Main event loop — dispatches events to registered handlers in causal order.

The loop enforces:
1. Strict temporal ordering (no future information)
2. Causal priority within each timestamp
3. Handler isolation (one handler cannot see another's yet-unprocessed events)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Callable

from backtesting.event_engine.event_queue import EventQueue
from backtesting.event_engine.event_types import EventType
from backtesting.event_engine.events import Event

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], list[Event] | None]


class EventLoop:
    """
    Event-driven backtesting loop.

    Handlers register for specific EventTypes. When an event is dispatched,
    its handler may return new downstream events (e.g. a SignalEvent handler
    returns OrderEvents). These are pushed onto the queue and processed
    in correct causal order.
    """

    def __init__(self, max_events: int = 10_000_000) -> None:
        self._queue = EventQueue()
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._max_events = max_events
        self._events_processed = 0
        self._current_timestamp = None

    def register(self, event_type: EventType, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def submit(self, event: Event) -> None:
        self._queue.push(event)

    def submit_batch(self, events: list[Event]) -> None:
        for event in events:
            self._queue.push(event)

    def run(self) -> dict[str, int]:
        """
        Drain the event queue, dispatching each event to registered handlers.

        Returns event processing statistics.
        """
        self._events_processed = 0

        while not self._queue.empty:
            if self._events_processed >= self._max_events:
                logger.warning(
                    "Event loop hit max_events limit (%d). "
                    "Possible infinite loop or excessive event generation.",
                    self._max_events,
                )
                break

            event = self._queue.pop()
            self._current_timestamp = event.timestamp
            self._events_processed += 1

            handlers = self._handlers.get(event.event_type, [])
            for handler in handlers:
                downstream = handler(event)
                if downstream:
                    for child in downstream:
                        if child.timestamp < event.timestamp:
                            raise ValueError(
                                f"Causal violation: handler produced event at "
                                f"{child.timestamp} before current time {event.timestamp}"
                            )
                        self._queue.push(child)

        stats = self._queue.stats
        stats["total_processed"] = self._events_processed
        logger.info("Event loop completed: %d events processed", self._events_processed)
        return stats

    @property
    def events_processed(self) -> int:
        return self._events_processed

    @property
    def current_timestamp(self):
        return self._current_timestamp

    @property
    def queue_size(self) -> int:
        return len(self._queue)
