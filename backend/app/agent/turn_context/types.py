from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

InjectionKind = Literal["board", "progress", "textbook", "other"]


@dataclass(frozen=True)
class InjectionBlock:
    kind: InjectionKind
    content: str


@dataclass(frozen=True)
class TurnContextSnapshot:
    injections: tuple[InjectionBlock, ...]


def classify_injection_kind(content: str) -> InjectionKind:
    """Infer kind from system message content prefix."""
    if content.startswith("[user whiteboard"):
        return "board"
    if content.startswith("[session progress]"):
        return "progress"
    if content.startswith("[textbook excerpt]"):
        return "textbook"
    return "other"
