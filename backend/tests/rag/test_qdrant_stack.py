from unittest.mock import patch

from app.config import Settings
from app.rag.llamaindex_qdrant import build_qdrant_index_stack


def test_build_qdrant_index_stack_wires_constructors() -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key="sk-test",
        qdrant_url="http://qdrant.test:6333",
        qdrant_api_key="qd-test",
        qdrant_collection="test_collection",
        embedding_provider="openai",
        embedding_model="text-embedding-3-large",
    )
    fake_embed_model = object()

    with (
        patch("llama_index.core.StorageContext") as storage_context_cls,
        patch("llama_index.core.VectorStoreIndex") as index_cls,
        patch("app.rag.embeddings.build_embed_model", return_value=fake_embed_model) as build_embed,
        patch("llama_index.vector_stores.qdrant.QdrantVectorStore") as vector_store_cls,
        patch("qdrant_client.AsyncQdrantClient") as qdrant_client_cls,
        patch("app.rag.llamaindex_qdrant.QdrantTextbookStore") as store_cls,
    ):
        stack = build_qdrant_index_stack(settings)

    build_embed.assert_called_once_with(settings)
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
    index_cls.from_vector_store.assert_called_once_with(
        vector_store=vector_store_cls.return_value,
        storage_context=storage_context_cls.from_defaults.return_value,
        embed_model=fake_embed_model,
    )
    store_cls.assert_called_once_with(
        qdrant_client=qdrant_client_cls.return_value,
        collection_name="test_collection",
        index=index_cls.from_vector_store.return_value,
    )
    assert stack.index is index_cls.from_vector_store.return_value
    assert stack.store is store_cls.return_value
    assert stack.collection_name == "test_collection"
    assert stack.qdrant_client is qdrant_client_cls.return_value
