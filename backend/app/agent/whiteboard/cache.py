"""Per-room in-process cache of the AiBoard's current items.

The cache is NOT authoritative for the frontend — the frontend has its own
sliding-window render state. The cache exists so the board extractor can be
given an accurate "what's already on the board" context when deciding what
new items to emit for a sentence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agent.whiteboard.messages import AiBoardItem


@dataclass
class BoardCache:
    items: dict[str, AiBoardItem] = field(default_factory=dict)

    def current_items(self) -> list[AiBoardItem]:
        """Return a snapshot of current items. Mutating the returned list
        does not affect the cache."""
        return list(self.items.values())

    def apply(self, new_items: list[AiBoardItem]) -> None:
        """Upsert new items into the cache. Existing ids are replaced."""
        for item in new_items:
            self.items[item.id] = item
