"""YAML scenario format for scripted tutor↔student conversation runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.agent.grader.base import GradeResult


class TurnExpectation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_calls: list[str] = Field(default_factory=list)
    search_query_contains: list[str] = Field(default_factory=list)
    assistant_contains: list[str] = Field(default_factory=list)
    assistant_not_contains: list[str] = Field(default_factory=list)
    # Progression expectations — checked against the engine state AFTER the turn.
    # ``node_level`` maps node_id → required effective level (concept or problem).
    node_level: dict[str, str] = Field(default_factory=dict)
    focus_node: str | None = None
    next_suggestion_node: str | None = None
    # node_id → substring that must appear in that node's misconceptions list.
    misconceptions_contain: dict[str, str] = Field(default_factory=dict)


class ScenarioTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student: str
    board_text: str | None = None
    grader_result: GradeResult | None = None
    expect: TurnExpectation = Field(default_factory=TurnExpectation)


class ConversationScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    user_id: str | None = None
    doc_id: str | None = None
    board_text: str | None = None
    greeting: bool = True
    turns: list[ScenarioTurn]


def load_scenario(path: Path | str) -> ConversationScenario:
    raw_path = Path(path)
    data: Any = yaml.safe_load(raw_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{raw_path}: expected a YAML mapping at the top level")
    return ConversationScenario.model_validate(data)
