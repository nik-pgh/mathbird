"""Tests for local console runtime helpers."""

import pytest
from livekit import rtc
from livekit.agents.testing import fake_job_context
from livekit.protocol import agent_simulation as sim_pb

from app.agent.console.runtime import enable_text_only_job, local_text_job


@pytest.mark.asyncio
async def test_enable_text_only_job_sets_simulation_context() -> None:
    room = rtc.Room()
    with fake_job_context(room=room) as ctx:
        assert ctx.simulation_context() is None
        enable_text_only_job(ctx)
        sim_ctx = ctx.simulation_context()
        assert sim_ctx is not None
        assert sim_ctx.simulation_mode == sim_pb.SimulationMode.SIMULATION_MODE_TEXT


@pytest.mark.asyncio
async def test_local_text_job_yields_configured_context() -> None:
    async with local_text_job() as ctx:
        assert ctx.is_fake_job()
        sim_ctx = ctx.simulation_context()
        assert sim_ctx is not None
        assert sim_ctx.simulation_mode == sim_pb.SimulationMode.SIMULATION_MODE_TEXT
