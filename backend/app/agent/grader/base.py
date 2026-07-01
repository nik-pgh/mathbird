"""``Grader`` Protocol — a per-turn seam that evolves the student model.

A grader inspects one student turn (transcript text + whiteboard text) and the
current focus/syllabus context, and returns zero or more :class:`NodeUpdate`
directives that the agent applies to the :class:`~app.progress.engine.ProgressEngine`.
This decouples student-model evolution from the main LLM's memory: the model
advances every turn whether or not the tutor called a progress tool.

Add a new grader by:

1. Adding a module under ``app/agent/grader/`` that exposes a class
   implementing :class:`Grader`.
2. Adding the name to ``GraderName`` in ``app/config.py``.
3. Adding the corresponding branch in :func:`get_grader`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from app.progress.models import MasteryLevel


class NodeUpdate(BaseModel):
    """A single graded change to apply to a node.

    ``node_id`` is a concept or problem id from the syllabus. ``level`` raises
    the node's mastery (the engine applies it monotonically). ``force=True``
    lets the grader revise an earlier over-optimistic judgment downward.
    Misconception additions are appended (deduped); a non-empty list never
    clears existing ones.
    """

    model_config = ConfigDict(extra="forbid")

    node_id: str
    level: MasteryLevel | None = None
    force: bool = False
    misconception_additions: list[str] = Field(default_factory=list)
    clear_misconceptions: bool = False
    hint_given: bool = False
    note: str = ""


class GradeResult(BaseModel):
    """The full graded payload for one turn."""

    model_config = ConfigDict(extra="forbid")

    set_focus_node_id: str | None = None
    updates: list[NodeUpdate] = Field(default_factory=list)


@runtime_checkable
class Grader(Protocol):
    async def grade(
        self,
        *,
        turn_text: str,
        board_text: str | None,
        focus_node_id: str | None,
        levels: dict[str, MasteryLevel],
        syllabus_context: str,
        next_suggestion_node_id: str | None = None,
        next_suggestion_label: str | None = None,
        recommend_intent: str | None = None,
        recommend_directive: str | None = None,
        last_tutor_message: str | None = None,
    ) -> GradeResult: ...
