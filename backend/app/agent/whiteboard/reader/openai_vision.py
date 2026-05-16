"""Vision-LLM board reader using the OpenAI chat completions API.

The agent worker calls :meth:`interpret` with a PNG snapshot of the student's
canvas and gets back a single string — text plus inline LaTeX if the student
wrote math. Errors are swallowed and returned as an empty string so a transient
vision API failure never blocks the voice loop.
"""

from __future__ import annotations

import base64
import logging
from typing import Any

logger = logging.getLogger("mathbird.agent.whiteboard.openai_vision")

_SYSTEM_PROMPT = (
    "You are an OCR / handwriting recognizer for a student's math whiteboard. "
    "Return only what is written on the board. If the student wrote math, use "
    "inline LaTeX delimited by $...$. If the board is empty or unintelligible, "
    "return an empty string. Do not add commentary."
)


class OpenAIVisionBoardReader:
    def __init__(self, *, model: str, api_key: str | None) -> None:
        # Lazy import so installations that don't enable this reader never need
        # the openai package loaded at import time. ``openai`` is already a
        # transitive dep via ``livekit-agents[openai]``.
        from openai import AsyncOpenAI

        self.model = model
        self._client: Any = AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()

    async def interpret(self, png_bytes: bytes) -> str:
        if not png_bytes:
            return ""

        data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Read this whiteboard."},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
            )
        except Exception:
            logger.exception("OpenAIVisionBoardReader call failed")
            return ""

        try:
            return (completion.choices[0].message.content or "").strip()
        except (AttributeError, IndexError):
            logger.warning("OpenAIVisionBoardReader received an unexpected response shape")
            return ""
