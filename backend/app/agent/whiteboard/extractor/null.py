"""``NullExtractor`` — no-op default when ``BOARD_EXTRACTOR=null``."""

from __future__ import annotations

from app.agent.whiteboard.messages import AiBoardItem


class NullExtractor:
    async def extract(
        self,
        sentence: str,
        current_items: list[AiBoardItem],
        last_sentence: str | None,
    ) -> list[AiBoardItem]:
        return []
