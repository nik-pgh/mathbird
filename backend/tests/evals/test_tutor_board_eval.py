"""Unit tests for tutor board evaluation scoring."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evals.tutor_board import (
    TutorBoardGoldenCase,
    load_tutor_board_cases,
    score_extractor_case,
    score_reference_case,
)
from app.agent.whiteboard.messages import AiBoardText

GOLDEN_PATH = Path(__file__).resolve().parents[2] / "evals" / "golden" / "tutor_board.jsonl"


def test_load_golden_cases() -> None:
    cases = load_tutor_board_cases(GOLDEN_PATH)
    assert len(cases) >= 45
    axes = {case.axis for case in cases}
    assert axes == {"usage", "content", "reference", "card_kind", "grouping"}
    by_axis: dict[str, int] = {}
    for case in cases:
        by_axis[case.axis] = by_axis.get(case.axis, 0) + 1
    for axis in axes:
        assert by_axis[axis] >= 8, f"expected at least 8 {axis} cases, got {by_axis[axis]}"


def test_score_extractor_emit_pass() -> None:
    case = TutorBoardGoldenCase.model_validate(
        {
            "id": "x",
            "axis": "usage",
            "description": "d",
            "extractor": {"sentence": "s", "current_items": []},
            "expected_extractor": {"emit": True, "min_items": 1, "kinds": ["text"]},
        }
    )
    score = score_extractor_case(
        case,
        [AiBoardText(kind="text", id="eq1", markdown="$x=1$")],
    )
    assert score.passed


def test_score_extractor_forbidden_kind_fails() -> None:
    case = TutorBoardGoldenCase.model_validate(
        {
            "id": "x",
            "axis": "card_kind",
            "description": "d",
            "extractor": {"sentence": "s", "current_items": []},
            "expected_extractor": {
                "emit": True,
                "kinds": ["plot"],
                "forbidden_kinds": ["text"],
            },
        }
    )
    score = score_extractor_case(
        case,
        [AiBoardText(kind="text", id="eq1", markdown="$x=1$")],
    )
    assert not score.passed
    assert any("forbidden kind" in failure for failure in score.failures)


def test_score_reference_board_pointing_pass() -> None:
    case = TutorBoardGoldenCase.model_validate(
        {
            "id": "x",
            "axis": "reference",
            "description": "d",
            "tutor_utterance": "Look at the equation on the board.",
            "expected_reference": {
                "references_board": True,
                "utterance_contains": ["board", "equation"],
            },
        }
    )
    score = score_reference_case(case)
    assert score.passed


def test_score_reference_forbidden_phrase_fails() -> None:
    case = TutorBoardGoldenCase.model_validate(
        {
            "id": "x",
            "axis": "reference",
            "description": "d",
            "tutor_utterance": "I can't draw diagrams here.",
            "expected_reference": {
                "references_board": False,
                "utterance_not_contains": ["can't draw"],
            },
        }
    )
    score = score_reference_case(case)
    assert not score.passed


def test_score_grouping_append_rejects_new_id() -> None:
    case = TutorBoardGoldenCase.model_validate(
        {
            "id": "x",
            "axis": "grouping",
            "description": "d",
            "extractor": {
                "sentence": "s",
                "current_items": [{"kind": "text", "id": "eq1", "markdown": "$x=1$"}],
            },
            "expected_extractor": {
                "emit": True,
                "grouping_action": "append",
                "reuse_id": "eq1",
            },
        }
    )
    score = score_extractor_case(
        case,
        [AiBoardText(kind="text", id="eq2", markdown="$x=2$")],
        current_items=[AiBoardText(kind="text", id="eq1", markdown="$x=1$")],
    )
    assert not score.passed
    assert any("append" in failure for failure in score.failures)


def test_score_grouping_create_rejects_reused_id() -> None:
    case = TutorBoardGoldenCase.model_validate(
        {
            "id": "x",
            "axis": "grouping",
            "description": "d",
            "extractor": {
                "sentence": "s",
                "current_items": [{"kind": "text", "id": "eq1", "markdown": "$x=1$"}],
            },
            "expected_extractor": {
                "emit": True,
                "grouping_action": "create",
                "forbidden_ids": ["eq1"],
            },
        }
    )
    score = score_extractor_case(
        case,
        [AiBoardText(kind="text", id="eq1", markdown="$x=1$ \\\\ $x=2$")],
        current_items=[AiBoardText(kind="text", id="eq1", markdown="$x=1$")],
    )
    assert not score.passed
    assert any("create" in failure or "forbidden id" in failure for failure in score.failures)


def test_score_grouping_append_passes_on_reused_id() -> None:
    case = TutorBoardGoldenCase.model_validate(
        {
            "id": "x",
            "axis": "grouping",
            "description": "d",
            "extractor": {
                "sentence": "s",
                "current_items": [{"kind": "text", "id": "eq1", "markdown": "$x=1$"}],
            },
            "expected_extractor": {
                "emit": True,
                "grouping_action": "append",
                "reuse_id": "eq1",
            },
        }
    )
    score = score_extractor_case(
        case,
        [AiBoardText(kind="text", id="eq1", markdown="$x=1$ \\\\ $x=2$")],
        current_items=[AiBoardText(kind="text", id="eq1", markdown="$x=1$")],
    )
    assert score.passed


def test_golden_rows_validate() -> None:
    for line in GOLDEN_PATH.read_text().splitlines():
        if not line.strip():
            continue
        TutorBoardGoldenCase.model_validate(json.loads(line))


@pytest.mark.live
async def test_live_extractor_on_seed_subset() -> None:
    from app.evals.tutor_board import evaluate_tutor_board_cases
    from app.agent.whiteboard.extractor.factory import get_board_extractor

    get_board_extractor.cache_clear()
    cases = [case for case in load_tutor_board_cases(GOLDEN_PATH) if case.id == "tb-use-001"]
    report = await evaluate_tutor_board_cases(cases, extractor=get_board_extractor())
    assert report.cases[0].case_id == "tb-use-001"
