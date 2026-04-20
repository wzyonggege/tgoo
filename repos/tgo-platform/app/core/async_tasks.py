from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine, TypeVar

_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()
_TaskResult = TypeVar("_TaskResult")


def spawn_background_task(
    coro: Coroutine[Any, Any, _TaskResult],
    *,
    logger: logging.Logger | None = None,
    error_message: str | None = None,
) -> asyncio.Task[_TaskResult]:
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)

    def _on_done(done_task: asyncio.Task[Any]) -> None:
        _BACKGROUND_TASKS.discard(done_task)
        try:
            exc = done_task.exception()
        except asyncio.CancelledError:
            return
        if exc is None or logger is None or not error_message:
            return
        logger.error(
            error_message,
            exc_info=(type(exc), exc, exc.__traceback__),
        )

    task.add_done_callback(_on_done)
    return task
