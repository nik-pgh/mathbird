"""LLM provider factory."""

from __future__ import annotations

from livekit.agents import llm as llm_base

from app.config import Settings


def build_llm(settings: Settings) -> llm_base.LLM:
    name = settings.llm_provider
    if name == "openai":
        from livekit.plugins import openai

        return openai.LLM(
            model=settings.llm_model,
            api_key=settings.openai_api_key or None,
            max_completion_tokens=settings.llm_max_tokens,
            _strict_tool_schema=False,
        )

    raise ValueError(f"Unknown LLM provider: {name}")
