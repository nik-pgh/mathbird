"""Optional Arize Phoenix tracing for LLM / RAG / function-tool calls.

Enabled via ``PHOENIX_ENABLED=true``. When enabled, this module configures
an OTLP exporter and patches the OpenAI + LlamaIndex client libraries so
every LLM completion, function tool call, and ``retriever.retrieve()``
invocation produces a span visible in Phoenix's trace UI (default
``http://localhost:6006``).

Disabled by default — production paths pay nothing. Install the optional
deps with ``uv sync --extra observability`` before enabling.

Architectural note: vendor imports (phoenix, openinference) are confined to
this module per the "vendor SDKs at boundaries" rule. Both backend
processes call ``setup_phoenix()`` near startup; it is idempotent so each
process only instruments once.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings

logger = logging.getLogger("mathbird.observability")

_initialized = False


def setup_phoenix() -> None:
    """Initialize Phoenix tracing if ``PHOENIX_ENABLED``. No-op otherwise.

    Safe to call multiple times — only the first call per process performs
    the instrumentation patching. When the optional ``observability`` deps
    are missing, logs a warning and returns rather than raising, so a
    misconfigured ``PHOENIX_ENABLED=true`` never crashes the worker.
    """
    global _initialized
    if _initialized:
        return

    settings = get_settings()
    if not settings.phoenix_enabled:
        return

    try:
        from openinference.instrumentation.llama_index import (
            LlamaIndexInstrumentor,
        )
        from openinference.instrumentation.openai import OpenAIInstrumentor
        from phoenix.otel import register
    except ImportError as exc:
        logger.warning(
            "PHOENIX_ENABLED=true but Phoenix instrumentation deps are missing "
            "(%s). Install with `uv sync --extra observability`.",
            exc,
        )
        return

    register_kwargs: dict[str, Any] = {
        "project_name": settings.phoenix_project,
        "auto_instrument": False,
    }
    if settings.phoenix_endpoint:
        register_kwargs["endpoint"] = settings.phoenix_endpoint

    tracer_provider = register(**register_kwargs)
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)

    logger.info(
        "Phoenix tracing enabled (project=%s, endpoint=%s)",
        settings.phoenix_project,
        settings.phoenix_endpoint or "default (localhost:6006)",
    )
    _initialized = True
