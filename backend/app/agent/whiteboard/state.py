"""Per-room mutable cache of the most recent user-board reading.

There is one instance per agent worker job (i.e. per room). The listener task
writes; ``WhiteboardAgent.on_user_turn_completed`` reads. Both run on the
same asyncio loop so a plain dataclass is enough — no locking required.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class BoardReading:
    card_id: str
    label: str
    text: str
    refreshed_at: float


@dataclass
class BoardState:
    readings: dict[str, BoardReading] = field(default_factory=dict)
    refreshed_at: float | None = None

    @property
    def user_text(self) -> str:
        parts = [
            f"{reading.label}:\n{reading.text.strip()}"
            for reading in sorted(self.readings.values(), key=lambda r: r.label)
            if reading.text.strip()
        ]
        return "\n\n".join(parts)

    @user_text.setter
    def user_text(self, text: str) -> None:
        self.record_reading(text)

    @property
    def is_blank(self) -> bool:
        return not self.user_text.strip()

    @is_blank.setter
    def is_blank(self, is_blank: bool) -> None:
        if is_blank:
            self.record_empty()

    def record_reading(
        self,
        text: str,
        *,
        card_id: str = "student-card-1",
        card_label: str | None = None,
    ) -> None:
        now = time.time()
        if text.strip():
            self.readings[card_id] = BoardReading(
                card_id=card_id,
                label=card_label or _default_card_label(card_id),
                text=text,
                refreshed_at=now,
            )
        else:
            self.readings.pop(card_id, None)
        self.refreshed_at = now

    def record_empty(self, *, card_id: str = "student-card-1") -> None:
        self.readings.pop(card_id, None)
        self.refreshed_at = time.time()

    def age_seconds(self) -> float | None:
        if self.refreshed_at is None:
            return None
        return max(0.0, time.time() - self.refreshed_at)


def _default_card_label(card_id: str) -> str:
    suffix = card_id.removeprefix("student-card-")
    return f"Student Card {suffix}" if suffix and suffix != card_id else "Student Card"
