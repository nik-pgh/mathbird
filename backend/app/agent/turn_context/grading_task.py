"""Background grading task scheduling."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("mathbird.agent.grader")


async def _run_grader_safe(coro: Coroutine[Any, Any, None]) -> None:
    try:
        await coro
    except Exception:
        logger.exception("background grader task failed")


@dataclass
class PendingGrader:
    _task: asyncio.Task[None] | None = None

    async def drain(self) -> None:
        """Await the in-flight grader task, if any. Swallows task exceptions (already logged)."""
        task = self._task
        if task is None:
            return
        self._task = None
        try:
            await task
        except Exception:
            pass

    def schedule(self, coro: Coroutine[Any, Any, None]) -> asyncio.Task[None]:
        """Schedule a new grader coroutine. Caller must drain() before scheduling if serializing."""
        task = asyncio.create_task(_run_grader_safe(coro))
        self._task = task
        return task
