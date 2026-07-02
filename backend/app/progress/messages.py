"""Wire format for the ``session_progress`` LiveKit data channel."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.progress.models import FocusPointer, MasteryLevel, ProgressSummary

SESSION_PROGRESS_TOPIC = "session_progress"


class ProblemProgressSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: str
    chapter_id: str
    concept_id: str
    label: str
    # Full ordinal mastery level (5 values). The pre-refactor wire carried
    # only three ("not_started" | "in_progress" | "mastered"); the
    # ``introduced`` / ``practicing`` / ``proficient`` levels are the
    # in-between states that make partial progress observable.
    status: MasteryLevel
    attempts: int = 0


class ConceptProgressSnapshot(BaseModel):
    """Concept-level progress row. Concept status is computed by the engine
    (``effective_level``) and is additive to the wire — older clients that
    ignore ``concepts`` keep rendering problem rows unaffected."""

    model_config = ConfigDict(extra="forbid")

    concept_id: str
    chapter_id: str
    label: str
    level: MasteryLevel
    has_open_misconceptions: bool = False


class SessionProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["snapshot", "patch"]
    focus: FocusPointer | None = None
    next_suggestion: FocusPointer | None = None
    summary: ProgressSummary
    nodes: list[ProblemProgressSnapshot] = []
    # Additive: pre-Phase-D payloads omit it and still validate.
    concepts: list[ConceptProgressSnapshot] = []
