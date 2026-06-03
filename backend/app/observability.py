"""Optional Arize Phoenix tracing for LLM / RAG / function-tool calls.

Enabled via ``PHOENIX_ENABLED=true``. When enabled, this module configures
an OTLP exporter and patches the OpenAI + LlamaIndex client libraries so
every LLM completion, function tool call, and ``retriever.retrieve()``
invocation produces a span visible in Phoenix's trace UI (default
``http://localhost:6006``).

Tracing is disabled by default (``PHOENIX_ENABLED=false``) so idle processes
pay no export cost; Phoenix/OpenInference deps are always installed.

Architectural note: vendor imports (phoenix, openinference) are confined to
this module per the "vendor SDKs at boundaries" rule. Both backend
processes call ``setup_phoenix()`` near startup; it is idempotent so each
process only instruments once.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.config import get_settings

logger = logging.getLogger("mathbird.observability")

_initialized = False


def setup_phoenix() -> None:
    """Initialize Phoenix tracing if ``PHOENIX_ENABLED``. No-op otherwise.

    Safe to call multiple times — only the first call per process performs
    the instrumentation patching. On missing deps (should not happen after
    ``uv sync``), logs a warning and returns rather than raising.
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
            "(%s). Re-run `uv sync` in backend/.",
            exc,
        )
        return

    register_kwargs: dict[str, Any] = {
        "project_name": settings.phoenix_project,
        "auto_instrument": False,
        "batch": True,
    }
    os.environ["PHOENIX_PROJECT_NAME"] = settings.phoenix_project
    if settings.phoenix_endpoint:
        os.environ["PHOENIX_COLLECTOR_ENDPOINT"] = settings.phoenix_endpoint
    if settings.phoenix_api_key:
        os.environ["PHOENIX_API_KEY"] = settings.phoenix_api_key

    tracer_provider = register(**register_kwargs)
    OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)
    LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)

    logger.info(
        "Phoenix tracing enabled (project=%s, endpoint=%s)",
        settings.phoenix_project,
        settings.phoenix_endpoint or "default (localhost:6006)",
    )
    _initialized = True
