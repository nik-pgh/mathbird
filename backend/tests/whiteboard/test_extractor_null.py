"""``NullExtractor`` always returns an empty list regardless of input.

It's the default when ``BOARD_EXTRACTOR=null`` so the system runs end to
end without an OpenAI key or extractor cost.
"""

from __future__ import annotations

from app.agent.whiteboard.extractor.null import NullExtractor
from app.agent.whiteboard.messages import AiBoardText


async def test_null_extractor_returns_empty_for_any_input() -> None:
    ex = NullExtractor()
    items = await ex.extract(
        sentence="Let's set up 2x + 5 = 10.",
        current_items=[],
        last_sentence=None,
    )
    assert items == []


async def test_null_extractor_ignores_current_items() -> None:
    ex = NullExtractor()
    items = await ex.extract(
        sentence="anything",
        current_items=[AiBoardText(kind="text", id="eq1", markdown="x=1")],
        last_sentence="prior",
    )
    assert items == []
