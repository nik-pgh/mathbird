"""Knowledge-tracing state persisted per user and document."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FocusPointer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter_id: str
    concept_id: str
    problem_id: str


ProblemStatus = Literal["not_started", "in_progress", "mastered"]


class ProblemProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ProblemStatus = "not_started"
    attempts: int = 0
    solved: bool = False
    explained: bool = False
    updated_at: str = ""


class ProgressSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mastered: int = 0
    in_progress: int = 0
    total: int = 0


class ProgressState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    doc_id: str
    updated_at: str
    focus: FocusPointer | None = None
    next_suggestion: FocusPointer | None = None
    nodes: dict[str, ProblemProgress] = Field(default_factory=dict)
