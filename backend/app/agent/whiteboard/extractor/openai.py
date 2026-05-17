"""``OpenAIBoardExtractor`` — board extractor backed by OpenAI structured
outputs.

The vendor SDK import lives only in this file; the rest of the agent uses
the duck-typed :class:`BoardExtractor` Protocol.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.agent.whiteboard.messages import AiBoardItem

logger = logging.getLogger("mathbird.agent.extractor")


class ExtractorResponse(BaseModel):
    items: list[AiBoardItem]


_SYSTEM_PROMPT = """\
You extract whiteboard items from a single sentence of a math tutor's
spoken reply. The tutor is explaining math to a student in a live voice
session.

You will receive:
- The sentence the tutor just said.
- The previous sentence (for continuation/revision context).
- The list of items already on the whiteboard (with their ids).

Emit zero or more AiBoardItem entries that should appear on the board
based on the sentence. Be selective — only emit items for content that
genuinely benefits from being visual:

- text: any equation, expression, or numeric value the tutor verbalized.
  Wrap math in $...$ LaTeX.
    Example sentence: "let's set up 2x + 5 = 10"
    → {"kind": "text", "id": "eq1", "markdown": "$2x + 5 = 10$"}

- plot: a function/curve the tutor is describing.
    Example sentence: "the parabola y = x squared opens upward"
    → {"kind": "plot", "id": "p1", "expression": "x**2"}

Do NOT emit ANY items for:

- Socratic questions, even ones containing math:
    "What happens when x is zero?"        → []
    "Does the rule p → q apply here?"     → []
    "What's the next step?"               → []

- Casual numeric references (numbers that aren't being computed or shown):
    "There are 3 cases to consider."      → []
    "Let's start with part (a)."          → []
    "Two minutes left in the session."    → []

- Meta-commentary referring to the board or prior work:
    "Let's look at that equation again."  → []
    "As we saw above..."                  → []
    "I've drawn the curve below."         → []

- Conversational filler:
    "Nice work."  "Let's see."  "Okay."  "Right, exactly."  "Hmm."   → []

- Restatement of an existing board item without revision:
    Current: $2x + 5 = 10$
    Sentence: "So we have 2x + 5 = 10."     → []
    (Don't re-emit; the item is already on the board.)

ID policy:
- If the sentence refines an item already on the board (e.g. updates an
  equation step), REUSE that item's existing id so the board updates in
  place rather than appending.
- For new items, pick the next id in a stable sequence:
    text items: eq1, eq2, eq3, ...
    plot items: p1, p2, p3, ...
  Inspect the current items list to determine which ids are taken.
- Never produce two items with the same id in one response.

DEFAULT TO EMPTY. If you are not confident the sentence introduces new
visual math content that the student will benefit from seeing, return
{"items": []}. False positives clutter the board and damage trust;
false negatives are recoverable in the next sentence.
"""


def _format_user_message(
    sentence: str,
    current_items: list[AiBoardItem],
    last_sentence: str | None,
) -> str:
    items_json = json.dumps(
        [item.model_dump() for item in current_items],
        ensure_ascii=False,
    )
    prev = last_sentence if last_sentence else "(none)"
    return (
        f"Current board items (JSON):\n{items_json}\n\n"
        f"Previous sentence: {prev}\n\n"
        f"Sentence to process: {sentence}"
    )


class OpenAIBoardExtractor:
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
        # ``client`` injection is used by unit tests; in production we
        # build an ``AsyncOpenAI`` client.
        self._client = client if client is not None else AsyncOpenAI(api_key=api_key)

    async def extract(
        self,
        sentence: str,
        current_items: list[AiBoardItem],
        last_sentence: str | None,
    ) -> list[AiBoardItem]:
        try:
            completion = await asyncio.wait_for(
                self._client.beta.chat.completions.parse(
                    model=self._model,
                    response_format=ExtractorResponse,
                    messages=[
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": _format_user_message(sentence, current_items, last_sentence),
                        },
                    ],
                ),
                timeout=self._timeout,
            )
        except TimeoutError:
            logger.warning(
                "board extractor timed out after %.2fs on sentence: %r",
                self._timeout,
                sentence[:80],
            )
            return []
        except Exception as exc:
            logger.warning(
                "board extractor call failed (%s); skipping sentence: %r",
                type(exc).__name__,
                sentence[:80],
            )
            return []

        try:
            parsed = completion.choices[0].message.parsed
        except (AttributeError, IndexError):
            logger.warning("board extractor returned malformed completion shape")
            return []

        if parsed is None:
            return []
        return list(parsed.items)
