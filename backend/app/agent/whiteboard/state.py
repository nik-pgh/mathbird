"""Per-room mutable cache of the most recent user-board reading.

There is one instance per agent worker job (i.e. per room). The listener task
writes; ``WhiteboardAgent.on_user_turn_completed`` reads. Both run on the
same asyncio loop so a plain dataclass is enough — no locking required.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class BoardState:
    user_text: str = ""
    is_blank: bool = True
    refreshed_at: float | None = None

    def record_reading(self, text: str) -> None:
        self.user_text = text
        self.is_blank = not text.strip()
        self.refreshed_at = time.time()

    def record_empty(self) -> None:
        self.user_text = ""
        self.is_blank = True
        self.refreshed_at = time.time()

    def age_seconds(self) -> float | None:
        if self.refreshed_at is None:
            return None
        return max(0.0, time.time() - self.refreshed_at)
