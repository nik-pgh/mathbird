"""Wire format for the ``session_progress`` LiveKit data channel."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.progress.models import FocusPointer, ProgressSummary

SESSION_PROGRESS_TOPIC = "session_progress"


class ProblemProgressSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_id: str
    chapter_id: str
    concept_id: str
    label: str
    status: Literal["not_started", "in_progress", "mastered"]
    attempts: int = 0


class SessionProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["snapshot", "patch"]
    focus: FocusPointer | None = None
    next_suggestion: FocusPointer | None = None
    summary: ProgressSummary
    nodes: list[ProblemProgressSnapshot] = []
