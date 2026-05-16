from app.config import Settings


def test_rag_settings_defaults_keep_null_retriever() -> None:
    settings = Settings()

    assert settings.rag_provider == "null"
    assert settings.qdrant_collection == "mathbird_documents"
    assert settings.embedding_model == "text-embedding-3-small"
    assert settings.rag_top_k == 4


def test_rag_settings_accept_llamaindex_qdrant() -> None:
    settings = Settings(rag_provider="llamaindex_qdrant")

    assert settings.rag_provider == "llamaindex_qdrant"
