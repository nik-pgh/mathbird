"""Runtime helpers for local text console and YAML simulations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from livekit.agents.testing import fake_job_context
from livekit.agents.utils import http_context

if TYPE_CHECKING:
    from livekit import rtc
    from livekit.agents import JobContext


def enable_text_only_job(ctx: JobContext) -> None:
    """Skip STT/TTS/VAD for fake jobs that interact over typed text only.

    LiveKit's ``AgentSession._text_only`` checks ``JobContext.simulation_context()``
    for ``SIMULATION_MODE_TEXT``. We synthesize a minimal dispatch for local scripts.
    """
    from livekit.agents.simulation import SimulationContext
    from livekit.protocol import agent_simulation as sim_pb

    dispatch = sim_pb.SimulationDispatch(
        mode=sim_pb.SimulationMode.SIMULATION_MODE_TEXT,
        simulation_run_id="local-text",
        scenario=sim_pb.Scenario(label="local"),
    )
    ctx._simulation_ctx = SimulationContext(dispatch, ctx)
    ctx._simulation_resolved = True


@asynccontextmanager
async def local_agent_runtime() -> AsyncIterator[None]:
    """HTTP session lifecycle for plugins running outside the LiveKit worker."""
    async with http_context.open():
        yield


@asynccontextmanager
async def local_text_job(*, room: rtc.Room | None = None) -> AsyncIterator[JobContext]:
    """Fake job + HTTP context + text-only simulation mode for local scripts."""
    async with local_agent_runtime():
        with fake_job_context(room=room) as ctx:
            enable_text_only_job(ctx)
            yield ctx
