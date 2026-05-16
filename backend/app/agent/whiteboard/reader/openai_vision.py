"""Vision-LLM board reader. Implementation lands in the next task."""

from __future__ import annotations


class OpenAIVisionBoardReader:
    def __init__(self, *, model: str, api_key: str | None) -> None:
        self.model = model
        self.api_key = api_key

    async def interpret(self, png_bytes: bytes) -> str:
        # Real implementation lands in Task 5.
        return ""
