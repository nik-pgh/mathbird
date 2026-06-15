"""Parse-once ingestion into multiple embedding collections.

LlamaParse is expensive; :func:`ingest_pdf_all_embeddings` parses a PDF once,
then embeds the same nodes into one Qdrant collection per provider/model pair.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import EmbeddingProvider, Settings, get_settings
from app.rag.embeddings import embedding_collection_name
from app.rag.indexing import clone_nodes, parsed_document_to_nodes
from app.rag.llamaindex_qdrant import build_qdrant_index_stack, close_qdrant_client
from app.rag.llamaparse_parser import LlamaParseParser

# Documented embedding matrix from .env.example (HuggingFace omitted — optional extra).
DEFAULT_EMBEDDING_TARGETS: tuple[tuple[EmbeddingProvider, str], ...] = (
    ("openai", "text-embedding-3-small"),
    ("openai", "text-embedding-3-large"),
    ("cohere", "embed-english-v3.0"),
    ("cohere", "embed-v4.0"),
    ("voyage", "voyage-3-lite"),
    ("voyage", "voyage-3-large"),
)


@dataclass(frozen=True)
class EmbeddingIngestResult:
    embedding_provider: str
    embedding_model: str
    collection_name: str
    node_count: int


def _require_llamaparse(settings: Settings) -> None:
    if not settings.llamaparse_api_key:
        raise RuntimeError("LLAMAPARSE_API_KEY is required for PDF ingestion.")


def _embedding_api_key_field(provider: EmbeddingProvider) -> str:
    return {
        "openai": "openai_api_key",
        "cohere": "cohere_api_key",
        "voyage": "voyage_api_key",
        "huggingface": "",
    }[provider]


def _validate_embedding_target(settings: Settings, provider: EmbeddingProvider, model: str) -> None:
    field = _embedding_api_key_field(provider)
    if field and not getattr(settings, field):
        raise RuntimeError(
            f"{field.upper()} is required when ingesting with EMBEDDING_PROVIDER={provider!r}."
        )
    if provider == "huggingface":
        try:
            import llama_index.embeddings.huggingface  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "HuggingFace embeddings require: uv sync --extra embeddings-huggingface"
            ) from exc
    _ = embedding_collection_name(provider, model)


def build_parser(settings: Settings) -> LlamaParseParser:
    _require_llamaparse(settings)
    return LlamaParseParser(
        api_key=settings.llamaparse_api_key,
        tier=settings.llamaparse_tier,
        version=settings.llamaparse_version,
    )


async def parse_pdf_to_nodes(
    path: str,
    *,
    doc_id: str,
    settings: Settings | None = None,
) -> list[Any]:
    """Parse a PDF once and return LlamaIndex nodes (no embedding yet)."""
    base = settings or get_settings()
    parser = build_parser(base)
    filename = Path(path).name
    document = await parser.parse_pdf(path, doc_id=doc_id, filename=filename)
    return parsed_document_to_nodes(document)


async def insert_nodes_for_embedding(
    nodes: list[Any],
    *,
    base_settings: Settings,
    embedding_provider: EmbeddingProvider,
    embedding_model: str,
) -> EmbeddingIngestResult:
    """Embed and upsert *nodes* into the collection for one provider/model pair."""
    _validate_embedding_target(base_settings, embedding_provider, embedding_model)
    target_settings = base_settings.model_copy(
        update={
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
        }
    )
    stack = build_qdrant_index_stack(target_settings)
    try:
        batch = clone_nodes(nodes)
        if batch:
            await stack.index.ainsert_nodes(batch)
            await stack.store.ensure_payload_indexes()
        return EmbeddingIngestResult(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            collection_name=stack.collection_name,
            node_count=len(batch),
        )
    finally:
        await close_qdrant_client(stack.qdrant_client)


async def ingest_pdf_all_embeddings(
    path: str,
    *,
    doc_id: str,
    base_settings: Settings | None = None,
    targets: Sequence[tuple[EmbeddingProvider, str]] | None = None,
    parallel: bool = True,
) -> list[EmbeddingIngestResult]:
    """Parse *path* once, then index the same nodes into every embedding collection."""
    base = base_settings or get_settings()
    matrix = tuple(targets or DEFAULT_EMBEDDING_TARGETS)
    if not matrix:
        raise ValueError("At least one embedding target is required.")

    for provider, model in matrix:
        _validate_embedding_target(base, provider, model)

    nodes = await parse_pdf_to_nodes(path, doc_id=doc_id, settings=base)
    if not nodes:
        return [
            EmbeddingIngestResult(
                embedding_provider=provider,
                embedding_model=model,
                collection_name=embedding_collection_name(provider, model),
                node_count=0,
            )
            for provider, model in matrix
        ]

    async def _one(provider: EmbeddingProvider, model: str) -> EmbeddingIngestResult:
        return await insert_nodes_for_embedding(
            nodes,
            base_settings=base,
            embedding_provider=provider,
            embedding_model=model,
        )

    if parallel:
        results = await asyncio.gather(*(_one(provider, model) for provider, model in matrix))
        return list(results)

    results: list[EmbeddingIngestResult] = []
    for provider, model in matrix:
        results.append(await _one(provider, model))
    return results
