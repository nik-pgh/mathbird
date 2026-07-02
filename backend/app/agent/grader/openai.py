"""``OpenAIGrader`` — grader backed by OpenAI structured outputs.

The vendor SDK import lives only in this file; the rest of the agent uses the
duck-typed :class:`Grader` Protocol. Mirrors
:class:`~app.agent.whiteboard.extractor.openai.OpenAIBoardExtractor` exactly:
keyword-only constructor, ``client`` injection for tests, ``asyncio.wait_for``
timeout, degrade-to-empty on any failure.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.agent.grader.base import Grader, GradeResult, NodeUpdate
from app.progress.models import MasteryLevel

logger = logging.getLogger("mathbird.agent.grader")


# Pydantic emits ``anyOf`` for a plain Optional Literal, which OpenAI's
# Structured Outputs API accepts (it rejects ``oneOf``). Keep ``level`` as a
# plain Optional[str] field with the JSON-Schema enum copied in by hand below.
class _GradedNode(BaseModel):
    node_id: str
    level: MasteryLevel | None = None
    force: bool = False
    misconception_additions: list[str] = Field(default_factory=list)
    clear_misconceptions: bool = False
    hint_given: bool = False
    note: str = ""


class _GradeResponse(BaseModel):
    set_focus_node_id: str | None = None
    updates: list[_GradedNode] = Field(default_factory=list)


_SYSTEM_PROMPT = """\
You are a per-turn grader for a voice math tutor. After each student turn you \
assess what the student demonstrated and emit zero or more node updates that \
advance the student model.

You will receive:
- turn_text: everything the student said this turn.
- board_text: the current text on the student's whiteboard (may be null).
- focus_node_id: the concept or problem id the session is anchored on (may be null).
- levels: a map of node_id → current mastery level for nearby nodes.
- syllabus_context: the focus problem's statement, its parent concept, and \
adjacent problems (a short text block).
- next_suggestion_node_id / next_suggestion_label: the engine's current next \
suggestion candidate (may be null).
- recommend_intent / recommend_directive: what the tutor was trying to do in \
the previous message (may be null).
- last_tutor_message: the tutor message immediately before this student turn \
(may be null).

Mastery levels are ordinal: not_started < introduced < practicing < proficient < mastered.
- introduced: the concept/problem has been presented or opened.
- practicing: the student is actively working on it.
- proficient: the student produced a correct solution.
- mastered: the student both solved it AND explained the reasoning in their own words.

Emit updates ONLY when there is clear evidence in this turn. Prefer false \
negatives (emit nothing) over speculative promotions — over-advancing the \
model breaks the tutor's pacing.

Rules:
- ``level`` should reflect what the student DEMONSTRATED THIS TURN, not what \
they were told. Reading an explanation aloud is not mastery.
- Set ``mastered`` only when the student gave a correct answer AND a correct \
explanation in their own words. Partial or imitated reasoning stays at \
practicing/proficient.
- ``misconception_additions`` should capture specific, named errors \
(e.g. "confused matrix transpose with inverse", "sign error distributing the \
negative"). Phrase each as a reusable diagnostic, not a turn transcript.
- ``clear_misconceptions=true`` only when the student explicitly corrected a \
previously recorded error this turn.
- ``hint_given=true`` when ``last_tutor_message`` gave a substantive hint \
toward the focus node. Do not infer hints from the student turn alone.
- Target the focus node primarily; only touch other nodes when the student's \
work this turn clearly pertains to them (e.g. a prerequisite they reused).
- ``set_focus_node_id``: when ``recommend_intent`` is ``introduce`` and \
``next_suggestion_node_id`` is present, set it to that id when the student \
engages with the topic this turn — e.g. agrees to start ("yes", "ok", "let's \
go"), asks to continue ("current focus"), or answers a tutor question about \
prior knowledge ("almost nothing", "nothing", "a little about vectors"). Leave \
null only for empty turns, explicit redirects ("skip", "different problem"), \
or clear off-topic chatter.

If nothing in this turn supports an update, return {"updates": []}.
"""


def _format_user_message(
    turn_text: str,
    board_text: str | None,
    focus_node_id: str | None,
    levels: dict[str, MasteryLevel],
    syllabus_context: str,
    next_suggestion_node_id: str | None,
    next_suggestion_label: str | None,
    recommend_intent: str | None,
    recommend_directive: str | None,
    last_tutor_message: str | None,
) -> str:
    return (
        f"focus_node_id: {focus_node_id or '(none)'}\n"
        f"levels: {json.dumps(levels, ensure_ascii=False)}\n"
        f"next_suggestion_node_id: {next_suggestion_node_id or '(none)'}\n"
        f"next_suggestion_label: {next_suggestion_label or '(none)'}\n"
        f"recommend_intent: {recommend_intent or '(none)'}\n"
        f"recommend_directive: {recommend_directive or '(none)'}\n"
        f"syllabus_context:\n{syllabus_context or '(none)'}\n\n"
        f"last_tutor_message:\n{last_tutor_message or '(none)'}\n\n"
        f"board_text:\n{board_text or '(empty)'}\n\n"
        f"turn_text:\n{turn_text}"
    )


class OpenAIGrader(Grader):
    def __init__(
        self,
        *,
        model: str,
        timeout: float,
        api_key: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._timeout = timeout
        # ``client`` injection is used by unit tests; in production we build
        # an ``AsyncOpenAI`` client.
        self._client = client if client is not None else AsyncOpenAI(api_key=api_key)

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
    ) -> GradeResult:
        try:
            completion = await asyncio.wait_for(
                self._client.beta.chat.completions.parse(
                    model=self._model,
                    response_format=_GradeResponse,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": _format_user_message(
                                turn_text,
                                board_text,
                                focus_node_id,
                                levels,
                                syllabus_context,
                                next_suggestion_node_id,
                                next_suggestion_label,
                                recommend_intent,
                                recommend_directive,
                                last_tutor_message,
                            ),
                        },
                    ],
                ),
                timeout=self._timeout,
            )
        except TimeoutError:
            logger.warning(
                "grader timed out after %.2fs on turn: %r",
                self._timeout,
                turn_text[:80],
            )
            return GradeResult()
        except Exception as exc:
            logger.warning(
                "grader call failed (%s); skipping turn: %r",
                type(exc).__name__,
                turn_text[:80],
            )
            return GradeResult()

        try:
            parsed = completion.choices[0].message.parsed
        except (AttributeError, IndexError):
            logger.warning("grader returned malformed completion shape")
            return GradeResult()

        if parsed is None:
            return GradeResult()
        return GradeResult(
            set_focus_node_id=parsed.set_focus_node_id,
            updates=[
                NodeUpdate(
                    node_id=u.node_id,
                    level=u.level,
                    force=u.force,
                    misconception_additions=list(u.misconception_additions),
                    clear_misconceptions=u.clear_misconceptions,
                    hint_given=u.hint_given,
                    note=u.note,
                )
                for u in parsed.updates
            ]
        )
