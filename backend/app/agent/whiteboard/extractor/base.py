"""``BoardExtractor`` Protocol.

A board extractor takes one sentence of the agent's spoken reply, the items
currently on the AiBoard, and (optionally) the previous sentence, and
returns the AiBoard items that should be added or revised for this
sentence. Implementations are duck-typed.

Add a new extractor by:

1. Adding a module under ``app/agent/whiteboard/extractor/`` that exposes
   a class implementing :class:`BoardExtractor`.
2. Adding the name to ``BoardExtractorName`` in ``app/config.py``.
3. Adding the corresponding branch in :func:`get_board_extractor`.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.agent.whiteboard.messages import AiBoardItem


@runtime_checkable
class BoardExtractor(Protocol):
    async def extract(
        self,
        sentence: str,
        current_items: list[AiBoardItem],
        last_sentence: str | None,
    ) -> list[AiBoardItem]: ...
