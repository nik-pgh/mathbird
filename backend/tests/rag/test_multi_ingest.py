from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from llama_index.core.schema import TextNode

from app.config import Settings
from app.rag.indexing import clone_nodes, parsed_document_to_nodes
from app.rag.multi_ingest import (
    DEFAULT_EMBEDDING_TARGETS,
    EmbeddingIngestResult,
    MultiIngestEvent,
    ingest_pdf_all_embeddings,
    insert_nodes_for_embedding,
    parse_pdf_to_nodes,
)
from app.rag.parsing import ParsedBlock, ParsedDocument, ParsedPage


def _sample_document() -> ParsedDocument:
    return ParsedDocument(
        doc_id="doc-1",
        filename="book.pdf",
        pages=[
            ParsedPage(
                page_number=1,
                text="Problem 1.",
                blocks=[
                    ParsedBlock(
                        block_id="doc-1:p1:b1",
                        page_number=1,
                        block_type="exercise",
                        text="Problem 1. Solve x.",
                        exercise_number="1",
                    )
                ],
            )
        ],
    )


def test_clone_nodes_preserves_ids_and_metadata() -> None:
    original = parsed_document_to_nodes(_sample_document())
    clones = clone_nodes(original)

    assert len(clones) == 1
    assert clones[0].id_ == original[0].id_
    assert clones[0].get_content() == original[0].get_content()
    assert clones[0].metadata == original[0].metadata
    assert clones[0] is not original[0]


@pytest.mark.asyncio
async def test_parse_pdf_to_nodes_uses_parser_once() -> None:
    settings = Settings(
        _env_file=None,
        llamaparse_api_key="llx-test",
    )
    fake_document = _sample_document()
    parser = MagicMock()
    parser.parse_pdf = AsyncMock(return_value=fake_document)

    with patch("app.rag.multi_ingest.build_parser", return_value=parser):
        nodes = await parse_pdf_to_nodes("/tmp/book.pdf", doc_id="doc-1", settings=settings)

    parser.parse_pdf.assert_awaited_once_with(
        "/tmp/book.pdf",
        doc_id="doc-1",
        filename="book.pdf",
    )
    assert len(nodes) == 1
    assert nodes[0].metadata["exercise_number"] == "1"


@pytest.mark.asyncio
async def test_insert_nodes_for_embedding_clones_before_insert() -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key="sk-test",
        qdrant_url="http://qdrant.test:6333",
    )
    nodes = parsed_document_to_nodes(_sample_document())
    fake_stack = MagicMock()
    fake_stack.collection_name = "mathbird_openai_text_embedding_3_large"
    fake_stack.index.ainsert_nodes = AsyncMock()
    fake_stack.store.ensure_payload_indexes = AsyncMock()
    fake_stack.qdrant_client = object()

    with (
        patch("app.rag.multi_ingest.build_qdrant_index_stack", return_value=fake_stack) as build,
        patch("app.rag.multi_ingest.close_qdrant_client", new=AsyncMock()) as close_client,
        patch("app.rag.multi_ingest.clone_nodes", wraps=clone_nodes) as clone,
    ):
        result = await insert_nodes_for_embedding(
            nodes,
            base_settings=settings,
            embedding_provider="openai",
            embedding_model="text-embedding-3-large",
        )

    build.assert_called_once()
    called_settings = build.call_args.args[0]
    assert called_settings.embedding_provider == "openai"
    assert called_settings.embedding_model == "text-embedding-3-large"
    clone.assert_called_once_with(nodes)
    inserted = fake_stack.index.ainsert_nodes.await_args.args[0]
    assert inserted[0] is not nodes[0]
    fake_stack.store.ensure_payload_indexes.assert_awaited_once()
    close_client.assert_awaited_once_with(fake_stack.qdrant_client)
    assert result.collection_name == "mathbird_openai_text_embedding_3_large"
    assert result.node_count == 1


@pytest.mark.asyncio
async def test_ingest_pdf_all_embeddings_parses_once_and_indexes_all_targets() -> None:
    settings = Settings(
        _env_file=None,
        llamaparse_api_key="llx-test",
        openai_api_key="sk-test",
        cohere_api_key="cohere-test",
        voyage_api_key="voyage-test",
    )
    nodes = [TextNode(text="chunk", id_="node-1")]
    parse_mock = AsyncMock(return_value=nodes)
    insert_mock = AsyncMock(
        side_effect=[
            EmbeddingIngestResult(
                embedding_provider=provider,
                embedding_model=model,
                collection_name=f"collection_{provider}_{model}",
                node_count=1,
            )
            for provider, model in DEFAULT_EMBEDDING_TARGETS
        ]
    )

    with (
        patch("app.rag.multi_ingest.parse_pdf_to_nodes", parse_mock),
        patch("app.rag.multi_ingest.insert_nodes_for_embedding", insert_mock),
    ):
        results = await ingest_pdf_all_embeddings(
            "/tmp/book.pdf",
            doc_id="doc-1",
            base_settings=settings,
            parallel=False,
        )

    parse_mock.assert_awaited_once()
    assert insert_mock.await_count == len(DEFAULT_EMBEDDING_TARGETS)
    assert len(results.successes) == len(DEFAULT_EMBEDDING_TARGETS)
    assert results.failures == ()


@pytest.mark.asyncio
async def test_ingest_pdf_all_embeddings_requires_provider_api_key() -> None:
    settings = Settings(
        _env_file=None,
        llamaparse_api_key="llx-test",
        openai_api_key="",
    )

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        await ingest_pdf_all_embeddings(
            "/tmp/book.pdf",
            doc_id="doc-1",
            base_settings=settings,
            targets=[("openai", "text-embedding-3-small")],
        )


@pytest.mark.asyncio
async def test_ingest_pdf_all_embeddings_continue_on_error_collects_failures() -> None:
    settings = Settings(
        _env_file=None,
        llamaparse_api_key="llx-test",
        openai_api_key="sk-test",
        cohere_api_key="cohere-test",
        voyage_api_key="voyage-test",
    )
    nodes = [TextNode(text="chunk", id_="node-1")]
    targets = (
        ("openai", "text-embedding-3-small"),
        ("voyage", "voyage-3-lite"),
    )

    async def _insert(
        _nodes: list[TextNode],
        *,
        base_settings: Settings,
        embedding_provider: str,
        embedding_model: str,
    ):
        if embedding_provider == "voyage":
            raise RuntimeError("rate limited")
        return EmbeddingIngestResult(
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            collection_name=f"collection_{embedding_provider}_{embedding_model}",
            node_count=1,
        )

    with (
        patch("app.rag.multi_ingest.parse_pdf_to_nodes", AsyncMock(return_value=nodes)),
        patch("app.rag.multi_ingest.insert_nodes_for_embedding", side_effect=_insert),
    ):
        report = await ingest_pdf_all_embeddings(
            "/tmp/book.pdf",
            doc_id="doc-1",
            base_settings=settings,
            targets=targets,
            parallel=True,
            continue_on_error=True,
        )

    assert len(report.successes) == 1
    assert report.successes[0].embedding_provider == "openai"
    assert len(report.failures) == 1
    assert report.failures[0].embedding_provider == "voyage"
    assert "rate limited" in report.failures[0].error


@pytest.mark.asyncio
async def test_ingest_pdf_all_embeddings_emits_progress_events() -> None:
    settings = Settings(
        _env_file=None,
        llamaparse_api_key="llx-test",
        openai_api_key="sk-test",
        cohere_api_key="cohere-test",
        voyage_api_key="voyage-test",
    )
    nodes = [TextNode(text="chunk", id_="node-1")]
    targets = (("openai", "text-embedding-3-small"),)
    events: list[MultiIngestEvent] = []

    async def _insert(*_args, **_kwargs) -> EmbeddingIngestResult:
        return EmbeddingIngestResult(
            embedding_provider="openai",
            embedding_model="text-embedding-3-small",
            collection_name="mathbird_openai_text_embedding_3_small",
            node_count=1,
        )

    with (
        patch("app.rag.multi_ingest.parse_pdf_to_nodes", AsyncMock(return_value=nodes)),
        patch("app.rag.multi_ingest.insert_nodes_for_embedding", side_effect=_insert),
    ):
        await ingest_pdf_all_embeddings(
            "/tmp/book.pdf",
            doc_id="doc-1",
            base_settings=settings,
            targets=targets,
            parallel=False,
            on_progress=events.append,
        )

    kinds = [event.kind for event in events]
    assert kinds == ["parse_start", "parse_done", "embed_start", "embed_done", "all_done"]
    assert events[1].node_count == 1
    assert events[2].target_index == 1
    assert events[3].node_count == 1
