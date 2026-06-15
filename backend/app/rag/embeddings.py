"""Embedding model factory for the LlamaIndex + Qdrant retriever.

Vendor SDK imports stay in this module; ``app.rag.retriever`` calls
:func:`build_embed_model` only. Adding a provider = branch here + Literal in
``app.config.Settings`` + dep in ``pyproject.toml``.
"""

from __future__ import annotations

import re
from typing import Any

from app.config import Settings


def embedding_collection_name(
    provider: str,
    model: str,
    *,
    prefix: str = "mathbird",
) -> str:
    """Stable Qdrant collection slug for a provider + model pair."""
    slug = re.sub(r"[^a-z0-9]+", "_", f"{provider}_{model}".lower()).strip("_")
    return f"{prefix}_{slug}"


def build_embed_model(settings: Settings) -> Any:
    """Return a LlamaIndex ``BaseEmbedding`` for ``settings.embedding_provider``."""
    provider = settings.embedding_provider
    model = settings.embedding_model

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai.")
        from llama_index.embeddings.openai import OpenAIEmbedding

        return OpenAIEmbedding(model=model, api_key=settings.openai_api_key)

    if provider == "cohere":
        if not settings.cohere_api_key:
            raise RuntimeError("COHERE_API_KEY is required when EMBEDDING_PROVIDER=cohere.")
        from llama_index.embeddings.cohere import CohereEmbedding

        return CohereEmbedding(model_name=model, cohere_api_key=settings.cohere_api_key)

    if provider == "voyage":
        if not settings.voyage_api_key:
            raise RuntimeError("VOYAGE_API_KEY is required when EMBEDDING_PROVIDER=voyage.")
        from llama_index.embeddings.voyageai import VoyageEmbedding

        return VoyageEmbedding(model_name=model, voyage_api_key=settings.voyage_api_key)

    if provider == "huggingface":
        try:
            from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        except ImportError as exc:
            raise RuntimeError(
                "HuggingFace embeddings require the optional extra. "
                "Install with: uv sync --extra embeddings-huggingface"
            ) from exc

        return HuggingFaceEmbedding(model_name=model)

    raise ValueError(f"Unsupported embedding provider: {provider!r}")
