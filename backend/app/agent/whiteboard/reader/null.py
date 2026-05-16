"""No-op reader. Default. Lets the feature ship without paying for vision calls."""

from __future__ import annotations


class NullBoardReader:
    async def interpret(self, png_bytes: bytes) -> str:
        return ""
