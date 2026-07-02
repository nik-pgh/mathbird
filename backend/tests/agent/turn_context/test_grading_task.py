"""Tests for PendingGrader background grading helper."""

from __future__ import annotations

import asyncio

from app.agent.turn_context.grading_task import PendingGrader


async def test_drain_awaits_previous_task() -> None:
    order: list[str] = []

    async def work() -> None:
        order.append("start")
        await asyncio.sleep(0.01)
        order.append("done")

    pending = PendingGrader()
    pending.schedule(work())
    await asyncio.sleep(0)
    assert order == ["start"]
    await pending.drain()
    assert order == ["start", "done"]


async def test_drain_swallows_grade_failure() -> None:
    async def fail() -> None:
        raise RuntimeError("grade failed")

    pending = PendingGrader()
    pending.schedule(fail())
    await pending.drain()


async def test_schedule_returns_task() -> None:
    async def noop() -> None:
        return None

    pending = PendingGrader()
    task = pending.schedule(noop())
    assert isinstance(task, asyncio.Task)
    await pending.drain()
