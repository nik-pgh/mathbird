"""``get_grader`` — env-driven factory for student-model graders."""

from __future__ import annotations

from functools import lru_cache

from app.agent.grader.base import Grader
from app.config import get_settings


@lru_cache
def get_grader() -> Grader:
    """Return the configured grader.

    Reads ``GRADER`` once and caches the instance. Restart the worker to pick
    up env changes; tests should call ``get_grader.cache_clear()``.
    """
    settings = get_settings()
    name = settings.grader

    if name == "null":
        from .null import NullGrader

        return NullGrader()

    if name == "openai":
        from .openai import OpenAIGrader

        return OpenAIGrader(
            model=settings.grader_model,
            timeout=settings.grader_timeout_seconds,
            api_key=settings.openai_api_key or None,
        )

    raise ValueError(f"Unknown grader: {name}")
