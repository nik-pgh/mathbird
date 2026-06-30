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
async def test_resolve_local_identity_uses_sim_settings() -> None:
    from app.agent.console.identity import resolve_local_identity

    settings = SimpleNamespace(
        sim_user_id="sim-user",
        sim_active_doc_id="sim-doc",
        sim_interactive=False,
    )

    user_id, doc_id = await resolve_local_identity(settings)  # type: ignore[arg-type]

    assert user_id == "sim-user"
    assert doc_id == "sim-doc"


@pytest.mark.asyncio
async def test_resolve_session_identity_reads_participant_metadata() -> None:
    async def _wait_for_participant():
        return SimpleNamespace(metadata='{"user_id":"u2","active_doc_id":"d2"}')

    ctx = SimpleNamespace(wait_for_participant=_wait_for_participant)

    user_id, doc_id = await resolve_session_identity(ctx)  # type: ignore[arg-type]

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
        Path(__file__).resolve().parents[2] / "simulations/scenarios/tutor_greeting.yaml"
    )
    await run_scenario(scenario_path, settings=settings)


# --------------------------------------------------------- progression assertions

def _engine_for_progression_tests():
    from app.progress.engine import ProgressEngine
    from app.progress.models import ProgressState
    from app.syllabus.models import Chapter, Concept, Problem, Syllabus

    syllabus = Syllabus(
        doc_id="doc-1",
        built_at="t",
        chapters=[
            Chapter(
                id="ch-1",
                number=1,
                title="Chapter 1",
                concepts=[
                    Concept(
                        id="ch-1-c-a",
                        title="Concept A",
                        problems=[
                            Problem(
                                id="ch-1-p-1",
                                kind="exercise",
                                label="Problem 1",
                                block_id="b1",
                                page_number=1,
                            ),
                            Problem(
                                id="ch-1-p-2",
                                kind="exercise",
                                label="Problem 2",
                                block_id="b2",
                                page_number=2,
                            ),
                        ],
                    )
                ],
            )
        ],
    )
    state = ProgressState(user_id="u1", doc_id="doc-1", updated_at="t")
    return ProgressEngine(syllabus=syllabus, state=state)


@pytest.mark.asyncio
async def test_assert_progression_passes_on_matching_level() -> None:
    engine = _engine_for_progression_tests()
    engine.set_focus("ch-1-p-1")  # → practicing
    run = _run_with_events([ChatMessage(role="assistant", content=["ok"])])
    expect = TurnExpectation(node_level={"ch-1-p-1": "practicing"}, focus_node="ch-1-p-1")
    # Should not raise.
    assert_turn_expectations(run, expect, turn_label="turn 1", engine=engine)


@pytest.mark.asyncio
async def test_assert_progression_fails_on_wrong_level() -> None:
    engine = _engine_for_progression_tests()
    engine.set_focus("ch-1-p-1")  # → practicing, not mastered
    run = _run_with_events([ChatMessage(role="assistant", content=["ok"])])
    expect = TurnExpectation(node_level={"ch-1-p-1": "mastered"})
    with pytest.raises(AssertionError, match="ch-1-p-1"):
        assert_turn_expectations(run, expect, turn_label="turn 1", engine=engine)


@pytest.mark.asyncio
async def test_assert_progression_checks_next_suggestion() -> None:
    engine = _engine_for_progression_tests()
    engine.record_mastery("ch-1-p-1", solved=True, explained=True)  # → mastered, next is p-2
    run = _run_with_events([ChatMessage(role="assistant", content=["ok"])])
    expect = TurnExpectation(next_suggestion_node="ch-1-p-2")
    assert_turn_expectations(run, expect, turn_label="turn 1", engine=engine)


@pytest.mark.asyncio
async def test_assert_progression_checks_misconception() -> None:
    engine = _engine_for_progression_tests()
    engine.record_misconception("ch-1-p-1", "sign error distributing the negative")
    run = _run_with_events([ChatMessage(role="assistant", content=["ok"])])
    expect = TurnExpectation(misconceptions_contain={"ch-1-p-1": "sign error"})
    assert_turn_expectations(run, expect, turn_label="turn 1", engine=engine)


@pytest.mark.asyncio
async def test_assert_progression_skipped_without_engine() -> None:
    """When no engine is passed, progression fields are silently ignored."""
    run = _run_with_events([ChatMessage(role="assistant", content=["ok"])])
    expect = TurnExpectation(node_level={"ch-1-p-1": "mastered"})
    # Should not raise — no engine supplied.
    assert_turn_expectations(run, expect, turn_label="turn 1")


def test_progression_demo_syllabus_fixture_loads() -> None:
    """The hand-authored fixture must deserialize into a Syllabus."""
    import json
    from pathlib import Path

    from app.syllabus.models import Syllabus

    fixture = (
        Path(__file__).resolve().parents[2]
        / "simulations/fixtures/progression_demo_syllabus.json"
    )
    syllabus = Syllabus.model_validate(json.loads(fixture.read_text(encoding="utf-8")))
    assert syllabus.doc_id == "progression-demo"
    # Two concepts with problems + the engine can track them.
    problems = [
        p for ch in syllabus.chapters for c in ch.concepts for p in c.problems
    ]
    assert len(problems) == 3

