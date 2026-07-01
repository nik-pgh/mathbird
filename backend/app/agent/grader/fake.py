"""``FakeGrader`` — scripted grader for deterministic simulation tests.

Each ``grade()`` call pops and returns the next queued :class:`GradeResult`.
When exhausted, it raises to surface mismatches between scenario turns and
expected grading calls.
"""

from __future__ import annotations

from collections import deque

from app.agent.grader.base import GradeResult, Grader
from app.progress.models import MasteryLevel


class FakeGrader(Grader):
    def __init__(self, results: list[GradeResult]) -> None:
        self._results: deque[GradeResult] = deque(results)

    async def grade(
        self,
        *,
        turn_text: str,  # noqa: ARG002
        board_text: str | None,  # noqa: ARG002
        focus_node_id: str | None,  # noqa: ARG002
        levels: dict[str, MasteryLevel],  # noqa: ARG002
        syllabus_context: str,  # noqa: ARG002
        next_suggestion_node_id: str | None = None,  # noqa: ARG002
        next_suggestion_label: str | None = None,  # noqa: ARG002
        recommend_intent: str | None = None,  # noqa: ARG002
        recommend_directive: str | None = None,  # noqa: ARG002
        last_tutor_message: str | None = None,  # noqa: ARG002
    ) -> GradeResult:
        if not self._results:
            raise RuntimeError("FakeGrader queue exhausted")
        return self._results.popleft()
