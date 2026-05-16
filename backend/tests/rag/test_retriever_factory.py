from unittest.mock import patch

from app.config import Settings
from app.rag import retriever as retriever_module
from app.rag.retriever import NullRetriever, get_retriever


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
    retriever_module._singleton = None
    retriever = get_retriever()

    assert isinstance(retriever, NullRetriever)


def test_get_retriever_builds_llamaindex_qdrant() -> None:
    retriever_module._singleton = None
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
