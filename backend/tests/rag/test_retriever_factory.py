from unittest.mock import MagicMock, patch

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
    settings = Settings(_env_file=None)

    assert settings.rag_provider == "null"
    assert settings.resolved_qdrant_collection == "mathbird_openai_text_embedding_3_small"
    assert settings.embedding_provider == "openai"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.rag_top_k == 4


def test_rag_settings_accept_llamaindex_qdrant() -> None:
    settings = Settings(rag_provider="llamaindex_qdrant")

    assert settings.rag_provider == "llamaindex_qdrant"


def test_get_retriever_defaults_to_null() -> None:
    settings = Settings(_env_file=None)

    with patch("app.rag.retriever.get_settings", return_value=settings):
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
        embedding_provider="openai",
        embedding_model="text-embedding-3-large",
    )
    fake_stack = MagicMock()
    fake_stack.index = object()
    fake_stack.store = object()

    with (
        patch(
            "app.rag.llamaindex_qdrant.build_qdrant_index_stack",
            return_value=fake_stack,
        ) as build,
        patch("app.rag.llamaparse_parser.LlamaParseParser") as parser_cls,
        patch("app.rag.llamaindex_qdrant.LlamaIndexQdrantRetriever") as retriever_cls,
    ):
        retriever = _build_llamaindex_qdrant_retriever(settings)

    build.assert_called_once_with(settings)
    parser_cls.assert_called_once_with(
        api_key="llx-test",
        tier="balanced",
        version="2026-01-01",
    )
    retriever_cls.assert_called_once_with(
        parser=parser_cls.return_value,
        index=fake_stack.index,
        store=fake_stack.store,
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
