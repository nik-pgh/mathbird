from __future__ import annotations

from types import SimpleNamespace

import pytest
import yaml
from livekit.agents.llm import ChatMessage, FunctionCall
from livekit.agents.voice.run_result import RunResult

from app.agent.session_factory import parse_participant_metadata, resolve_session_identity
from app.agent.simulation.assertions import assert_turn_expectations
from app.agent.simulation.scenarios import TurnExpectation, load_scenario


def test_parse_participant_metadata() -> None:
    user_id, doc_id = parse_participant_metadata(
        '{"user_id": "u1", "active_doc_id": "doc-a"}'
    )
    assert user_id == "u1"
    assert doc_id == "doc-a"


@pytest.mark.asyncio
async def test_resolve_session_identity_uses_sim_settings_on_fake_job() -> None:
    ctx = SimpleNamespace(is_fake_job=lambda: True)
    settings = SimpleNamespace(sim_user_id="sim-user", sim_active_doc_id="sim-doc")

    user_id, doc_id = await resolve_session_identity(ctx, settings)  # type: ignore[arg-type]

    assert user_id == "sim-user"
    assert doc_id == "sim-doc"


@pytest.mark.asyncio
async def test_resolve_session_identity_reads_participant_metadata() -> None:
    async def _wait_for_participant():
        return SimpleNamespace(metadata='{"user_id":"u2","active_doc_id":"d2"}')

    ctx = SimpleNamespace(
        is_fake_job=lambda: False,
        wait_for_participant=_wait_for_participant,
    )
    settings = SimpleNamespace(sim_user_id="", sim_active_doc_id="")

    user_id, doc_id = await resolve_session_identity(ctx, settings)  # type: ignore[arg-type]

    assert user_id == "u2"
    assert doc_id == "d2"


def test_load_scenario_from_yaml(tmp_path) -> None:
    path = tmp_path / "scenario.yaml"
    path.write_text(
        yaml.dump(
            {
                "name": "demo",
                "turns": [{"student": "hello", "expect": {"assistant_contains": ["hi"]}}],
            }
        ),
        encoding="utf-8",
    )

    scenario = load_scenario(path)

    assert scenario.name == "demo"
    assert len(scenario.turns) == 1
    assert scenario.turns[0].student == "hello"
    assert scenario.turns[0].expect.assistant_contains == ["hi"]


def _run_with_events(items) -> RunResult:
    run = RunResult(user_input="test", output_type=None)
    for item in items:
        run._item_added(item)
    run._mark_done_if_needed(None)
    return run


@pytest.mark.asyncio
async def test_assert_turn_expectations_detects_search_documents() -> None:
    run = _run_with_events(
        [
            FunctionCall(
                call_id="1",
                name="search_documents",
                arguments='{"query": "problem 3"}',
            ),
            ChatMessage(role="assistant", content=["What have you tried so far?"]),
        ]
    )
    expect = TurnExpectation(
        tool_calls=["search_documents"],
        search_query_contains=["problem 3"],
        assistant_contains=["?"],
    )

    assert_turn_expectations(run, expect, turn_label="turn 1")


@pytest.mark.asyncio
async def test_assert_turn_expectations_fails_when_tool_missing() -> None:
    run = _run_with_events(
        [ChatMessage(role="assistant", content=["Sure, the answer is 5."])]
    )
    expect = TurnExpectation(tool_calls=["search_documents"])

    with pytest.raises(AssertionError, match="search_documents"):
        assert_turn_expectations(run, expect, turn_label="turn 1")


@pytest.mark.live
@pytest.mark.asyncio
async def test_tutor_greeting_scenario_live() -> None:
    """Hits the real LLM — run with ``pytest -m live`` when debugging sims."""
    from pathlib import Path

    from app.config import get_settings
    from scripts.simulate_conversation import run_scenario

    settings = get_settings()
    if not settings.openai_api_key:
        pytest.skip("OPENAI_API_KEY not set")

    scenario_path = (
        Path(__file__).resolve().parents[1] / "simulations/scenarios/tutor_greeting.yaml"
    )
    await run_scenario(scenario_path, settings=settings)
