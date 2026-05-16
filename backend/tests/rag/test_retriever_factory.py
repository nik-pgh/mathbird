from unittest.mock import patch

import pytest

from app.config import Settings, get_settings
from app.rag import retriever as retriever_module
from app.rag.retriever import (
    NullRetriever,
    _build_llamaindex_qdrant_retriever,
    get_retriever,
)


@pytest.fixture(autouse=True)
def clear_retriever_state() -> None:
    retriever_module._singleton = None
    get_settings.cache_clear()
    yield
    retriever_module._singleton = None
    get_settings.cache_clear()


def test_rag_settings_defaults_keep_null_retriever() -> None:
    settings = Settings()

    assert settings.rag_provider == "null"
    assert settings.qdrant_collection == "mathbird_documents"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.rag_top_k == 4


def test_rag_settings_accept_llamaindex_qdrant() -> None:
    settings = Settings(rag_provider="llamaindex_qdrant")

    assert settings.rag_provider == "llamaindex_qdrant"


def test_get_retriever_defaults_to_null() -> None:
    retriever = get_retriever()

    assert isinstance(retriever, NullRetriever)


def test_get_retriever_builds_llamaindex_qdrant() -> None:
    settings = Settings(
        rag_provider="llamaindex_qdrant",
        llamaparse_api_key="llx-test",
        openai_api_key="sk-test",
    )

    with (
        patch("app.rag.retriever.get_settings", return_value=settings),
        patch("app.rag.retriever._build_llamaindex_qdrant_retriever") as build,
    ):
        build.return_value = object()
        retriever = get_retriever()

    assert retriever is build.return_value


def test_build_llamaindex_qdrant_retriever_wires_constructors_without_hybrid() -> None:
    settings = Settings(
        rag_provider="llamaindex_qdrant",
        llamaparse_api_key="llx-test",
        llamaparse_tier="balanced",
        llamaparse_version="2026-01-01",
        openai_api_key="sk-test",
        qdrant_url="http://qdrant.test:6333",
        qdrant_api_key="qd-test",
        qdrant_collection="test_collection",
        embedding_model="text-embedding-3-large",
    )

    with (
        patch("llama_index.core.StorageContext") as storage_context_cls,
        patch("llama_index.core.VectorStoreIndex") as index_cls,
        patch("llama_index.embeddings.openai.OpenAIEmbedding") as embedding_cls,
        patch("llama_index.vector_stores.qdrant.QdrantVectorStore") as vector_store_cls,
        patch("qdrant_client.AsyncQdrantClient") as qdrant_client_cls,
        patch("app.rag.llamaparse_parser.LlamaParseParser") as parser_cls,
        patch("app.rag.llamaindex_qdrant.QdrantTextbookStore") as store_cls,
        patch("app.rag.llamaindex_qdrant.LlamaIndexQdrantRetriever") as retriever_cls,
    ):
        retriever = _build_llamaindex_qdrant_retriever(settings)

    qdrant_client_cls.assert_called_once_with(
        url="http://qdrant.test:6333",
        api_key="qd-test",
    )
    vector_store_cls.assert_called_once_with(
        aclient=qdrant_client_cls.return_value,
        collection_name="test_collection",
    )
    storage_context_cls.from_defaults.assert_called_once_with(
        vector_store=vector_store_cls.return_value,
    )
    embedding_cls.assert_called_once_with(
        model="text-embedding-3-large",
        api_key="sk-test",
    )
    index_cls.from_vector_store.assert_called_once_with(
        vector_store=vector_store_cls.return_value,
        storage_context=storage_context_cls.from_defaults.return_value,
        embed_model=embedding_cls.return_value,
    )
    parser_cls.assert_called_once_with(
        api_key="llx-test",
        tier="balanced",
        version="2026-01-01",
    )
    store_cls.assert_called_once_with(
        qdrant_client=qdrant_client_cls.return_value,
        collection_name="test_collection",
        index=index_cls.from_vector_store.return_value,
    )
    retriever_cls.assert_called_once_with(
        parser=parser_cls.return_value,
        index=index_cls.from_vector_store.return_value,
        store=store_cls.return_value,
    )
    assert retriever is retriever_cls.return_value


def test_build_llamaindex_qdrant_retriever_requires_llamaparse_api_key() -> None:
    settings = Settings(
        rag_provider="llamaindex_qdrant",
        llamaparse_api_key="",
        openai_api_key="sk-test",
    )

    with pytest.raises(
        RuntimeError,
        match="LLAMAPARSE_API_KEY is required when RAG_PROVIDER=llamaindex_qdrant.",
    ):
        _build_llamaindex_qdrant_retriever(settings)


def test_build_llamaindex_qdrant_retriever_requires_openai_api_key() -> None:
    settings = Settings(
        rag_provider="llamaindex_qdrant",
        llamaparse_api_key="llx-test",
        openai_api_key="",
    )

    with pytest.raises(
        RuntimeError,
        match="OPENAI_API_KEY is required when RAG_PROVIDER=llamaindex_qdrant.",
    ):
        _build_llamaindex_qdrant_retriever(settings)
