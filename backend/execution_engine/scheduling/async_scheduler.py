"""
Async execution scheduler — manages concurrent child order execution.

Provides asyncio-compatible scheduling for child orders, supporting:
- Concurrent execution of multiple child orders
- Timed scheduling based on execution algorithm schedules
- Cancellation and modification of pending orders
- Future websocket integration compatibility

Statistical assumptions:
- Child orders within a parent are partially independent.
- Concurrent execution across parents requires coordination to avoid
  exceeding aggregate market impact limits.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

import pandas as pd

from execution_engine.execution_base import (
    ChildOrder,
    ExecutionResult,
    FillEvent,
    OrderStatus,
    ParentOrder,
)
from execution_engine.scheduling.execution_clock import ExecutionClock

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    child_order: ChildOrder
    scheduled_time: pd.Timestamp
    task: asyncio.Task | None = None
    completed: bool = False
    cancelled: bool = False


class AsyncExecutionScheduler:
    """
    Asyncio-based execution scheduler for child orders.

    Manages the lifecycle of child order execution, supporting:
    - Timed submission of child orders
    - Concurrent execution monitoring
    - Graceful cancellation
    - Order completion callbacks
    """

    def __init__(
        self,
        clock: ExecutionClock | None = None,
        max_concurrent: int = 10,
    ) -> None:
        self._clock = clock or ExecutionClock(simulation_mode=True)
        self._max_concurrent = max_concurrent
        self._pending: list[ScheduledTask] = []
        self._active: list[ScheduledTask] = []
        self._completed: list[ScheduledTask] = []
        self._semaphore: asyncio.Semaphore | None = None

    async def schedule_children(
        self,
        children: list[ChildOrder],
        fill_handler: Callable[[ChildOrder], Awaitable[FillEvent | None]],
        on_complete: Callable[[ChildOrder, FillEvent | None], Awaitable[None]] | None = None,
    ) -> list[FillEvent]:
        """
        Schedule and execute a batch of child orders.

        Parameters
        ----------
        children : child orders to execute (sorted by scheduled_time)
        fill_handler : async function that simulates/executes a child order
        on_complete : optional callback after each child completes
        """
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        fills: list[FillEvent] = []

        tasks = []
        for child in sorted(children, key=lambda c: c.scheduled_time or pd.Timestamp.min):
            task = asyncio.create_task(
                self._execute_child(child, fill_handler, on_complete, fills)
            )
            tasks.append(task)

        await asyncio.gather(*tasks, return_exceptions=True)
        return fills

    async def _execute_child(
        self,
        child: ChildOrder,
        fill_handler: Callable[[ChildOrder], Awaitable[FillEvent | None]],
        on_complete: Callable[[ChildOrder, FillEvent | None], Awaitable[None]] | None,
        fills: list[FillEvent],
    ) -> None:
        assert self._semaphore is not None
        async with self._semaphore:
            try:
                if child.scheduled_time:
                    now = self._clock.now
                    delay = (child.scheduled_time - now).total_seconds()
                    if delay > 0:
                        await asyncio.sleep(min(delay, 0.001))

                child.status = OrderStatus.ACTIVE

                fill = await fill_handler(child)

                if fill is not None:
                    child.apply_fill(fill)
                    fills.append(fill)

                if on_complete:
                    await on_complete(child, fill)

            except asyncio.CancelledError:
                child.status = OrderStatus.CANCELLED
                logger.info("Child order %s cancelled", child.child_id)
            except Exception as e:
                child.status = OrderStatus.REJECTED
                logger.error("Child order %s failed: %s", child.child_id, e)

    async def cancel_pending(self, parent_id: str) -> int:
        """Cancel all pending child orders for a parent. Returns count cancelled."""
        cancelled = 0
        for task in self._pending:
            if task.child_order.parent_id == parent_id and not task.completed:
                task.cancelled = True
                task.child_order.status = OrderStatus.CANCELLED
                if task.task and not task.task.done():
                    task.task.cancel()
                cancelled += 1
        return cancelled


class SyncExecutionScheduler:
    """
    Synchronous execution scheduler for backtesting/simulation.

    Processes child orders sequentially in scheduled-time order.
    No asyncio dependency — suitable for backtesting loops.
    """

    def __init__(self, clock: ExecutionClock | None = None) -> None:
        self._clock = clock or ExecutionClock(simulation_mode=True)

    def execute_all(
        self,
        children: list[ChildOrder],
        fill_handler: Callable[[ChildOrder], FillEvent | None],
    ) -> list[FillEvent]:
        fills = []
        for child in sorted(children, key=lambda c: c.scheduled_time or pd.Timestamp.min):
            if child.scheduled_time:
                self._clock.advance_to(child.scheduled_time)

            child.status = OrderStatus.ACTIVE

            try:
                fill = fill_handler(child)
                if fill is not None:
                    child.apply_fill(fill)
                    fills.append(fill)
            except Exception as e:
                child.status = OrderStatus.REJECTED
                logger.error("Child order %s failed: %s", child.child_id, e)

        return fills
