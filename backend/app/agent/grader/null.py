"""``NullGrader`` — no-op default when ``GRADER=null``.

Returns an empty :class:`GradeResult` every turn, so student-model evolution
is gated entirely on the LLM's manual tool calls (the pre-grader behavior).
"""

from __future__ import annotations

from app.agent.grader.base import GradeResult, Grader
from app.progress.models import MasteryLevel


class NullGrader(Grader):
    async def grade(
        self,
        *,
        turn_text: str,  # noqa: ARG002
        board_text: str | None,  # noqa: ARG002
        focus_node_id: str | None,  # noqa: ARG002
        levels: dict[str, MasteryLevel],  # noqa: ARG002
        syllabus_context: str,  # noqa: ARG002
    ) -> GradeResult:
        return GradeResult()
