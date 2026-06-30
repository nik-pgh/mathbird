"""Tests for v1 → v2 ProgressState migration on load."""

from __future__ import annotations

import json

from app.progress.models import NodeProgress, ProgressState


def _v1_payload() -> dict:
    """A pre-refactor progress.json payload (status field, no version)."""
    return {
        "user_id": "user-1",
        "doc_id": "doc-1",
        "updated_at": "2026-06-19T00:00:00+00:00",
        "focus": {"chapter_id": "ch-1", "concept_id": "ch-1-c-a", "problem_id": "ch-1-p-1"},
        "next_suggestion": {
            "chapter_id": "ch-1",
            "concept_id": "ch-1-c-a",
            "problem_id": "ch-1-p-2",
        },
        "nodes": {
            "ch-1-p-1": {
                "status": "in_progress",
                "attempts": 2,
                "solved": False,
                "explained": False,
                "updated_at": "t",
            },
            "ch-1-p-2": {
                "status": "mastered",
                "attempts": 3,
                "solved": True,
                "explained": True,
                "updated_at": "t",
            },
            "ch-1-p-3": {
                "status": "not_started",
                "attempts": 0,
                "solved": False,
                "explained": False,
                "updated_at": "",
            },
        },
    }


def test_v1_payload_loads_with_version_2() -> None:
    state = ProgressState.model_validate(_v1_payload())
    assert state.version == 2


def test_v1_in_progress_becomes_practicing() -> None:
    state = ProgressState.model_validate(_v1_payload())
    assert state.nodes["ch-1-p-1"].level == "practicing"
    # Preserved fields survive migration.
    assert state.nodes["ch-1-p-1"].attempts == 2


def test_v1_mastered_and_not_started_unchanged() -> None:
    state = ProgressState.model_validate(_v1_payload())
    assert state.nodes["ch-1-p-2"].level == "mastered"
    assert state.nodes["ch-1-p-3"].level == "not_started"


def test_v1_nodes_get_new_default_fields() -> None:
    state = ProgressState.model_validate(_v1_payload())
    for node in state.nodes.values():
        assert isinstance(node, NodeProgress)
        assert node.misconceptions == []
        assert node.hints_given == 0
        assert node.notes == ""


def test_v1_focus_and_next_suggestion_preserved() -> None:
    state = ProgressState.model_validate(_v1_payload())
    assert state.focus is not None
    assert state.focus.problem_id == "ch-1-p-1"
    assert state.next_suggestion is not None
    assert state.next_suggestion.problem_id == "ch-1-p-2"


def test_v1_json_round_trips_through_storage() -> None:
    """The exact path the store takes: json string → model_validate."""
    raw = json.dumps(_v1_payload())
    state = ProgressState.model_validate(json.loads(raw))
    assert state.nodes["ch-1-p-1"].level == "practicing"
    # Re-serializing as v2 no longer carries the old ``status`` key.
    redumped = json.loads(state.model_dump_json())
    assert "status" not in redumped["nodes"]["ch-1-p-1"]
    assert redumped["nodes"]["ch-1-p-1"]["level"] == "practicing"
    assert redumped["version"] == 2


def test_explicitly_v1_payload_also_migrates() -> None:
    payload = _v1_payload()
    payload["version"] = 1
    state = ProgressState.model_validate(payload)
    assert state.version == 2
    assert state.nodes["ch-1-p-1"].level == "practicing"
