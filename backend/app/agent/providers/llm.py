"""LLM provider factory."""

from __future__ import annotations

from livekit.agents import llm as llm_base

from app.config import Settings


def build_llm(settings: Settings) -> llm_base.LLM:
    name = settings.llm_provider
    if name == "openai":
        from livekit.plugins import openai

        # ``_strict_tool_schema=False`` is required because our whiteboard
        # tool ``update_ai_board`` takes ``items: list[AiBoardItem]`` where
        # ``AiBoardItem`` is a pydantic discriminated union. Strict-mode
        # JSON Schema rejects ``oneOf`` nested inside an array, which
        # OpenAI returns as a 400 ``invalid_function_parameters``. The
        # leading underscore on the kwarg is livekit's "internal but
        # supported" marker — see livekit/plugins/openai/llm.py.
        return openai.LLM(
            model=settings.llm_model,
            api_key=settings.openai_api_key or None,
            _strict_tool_schema=False,
        )

    raise ValueError(f"Unknown LLM provider: {name}")
