from unittest.mock import MagicMock, patch

import pytest

from app.config import Settings
from app.rag.embeddings import build_embed_model


def test_build_embed_model_openai() -> None:
    settings = Settings(
        _env_file=None,
        embedding_provider="openai",
        embedding_model="text-embedding-3-large",
        openai_api_key="sk-test",
    )

    with patch("llama_index.embeddings.openai.OpenAIEmbedding") as cls:
        build_embed_model(settings)

    cls.assert_called_once_with(model="text-embedding-3-large", api_key="sk-test")


def test_build_embed_model_openai_requires_api_key() -> None:
    settings = Settings(_env_file=None, embedding_provider="openai", openai_api_key="")

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY is required"):
        build_embed_model(settings)


def test_build_embed_model_cohere() -> None:
    settings = Settings(
        _env_file=None,
        embedding_provider="cohere",
        embedding_model="embed-v4.0",
        cohere_api_key="cohere-test",
    )

    with patch("llama_index.embeddings.cohere.CohereEmbedding") as cls:
        build_embed_model(settings)

    cls.assert_called_once_with(model_name="embed-v4.0", cohere_api_key="cohere-test")


def test_build_embed_model_cohere_requires_api_key() -> None:
    settings = Settings(_env_file=None, embedding_provider="cohere", cohere_api_key="")

    with pytest.raises(RuntimeError, match="COHERE_API_KEY is required"):
        build_embed_model(settings)


def test_build_embed_model_voyage() -> None:
    settings = Settings(
        _env_file=None,
        embedding_provider="voyage",
        embedding_model="voyage-3-lite",
        voyage_api_key="voyage-test",
    )

    with patch("llama_index.embeddings.voyageai.VoyageEmbedding") as cls:
        build_embed_model(settings)

    cls.assert_called_once_with(model_name="voyage-3-lite", voyage_api_key="voyage-test")


def test_build_embed_model_voyage_requires_api_key() -> None:
    settings = Settings(_env_file=None, embedding_provider="voyage", voyage_api_key="")

    with pytest.raises(RuntimeError, match="VOYAGE_API_KEY is required"):
        build_embed_model(settings)


def test_build_embed_model_huggingface() -> None:
    settings = Settings(
        _env_file=None,
        embedding_provider="huggingface",
        embedding_model="BAAI/bge-small-en-v1.5",
    )
    mock_cls = MagicMock()
    mock_module = MagicMock(HuggingFaceEmbedding=mock_cls)

    with patch.dict("sys.modules", {"llama_index.embeddings.huggingface": mock_module}):
        build_embed_model(settings)

    mock_cls.assert_called_once_with(model_name="BAAI/bge-small-en-v1.5")


@pytest.mark.parametrize(
    ("provider", "model", "expected"),
    [
        ("openai", "text-embedding-3-small", "mathbird_openai_text_embedding_3_small"),
        ("openai", "text-embedding-3-large", "mathbird_openai_text_embedding_3_large"),
        ("cohere", "embed-english-v3.0", "mathbird_cohere_embed_english_v3_0"),
        ("cohere", "embed-v4.0", "mathbird_cohere_embed_v4_0"),
        ("voyage", "voyage-3-lite", "mathbird_voyage_voyage_3_lite"),
        ("voyage", "voyage-3-large", "mathbird_voyage_voyage_3_large"),
    ],
)
def test_embedding_collection_name(provider: str, model: str, expected: str) -> None:
    from app.rag.embeddings import embedding_collection_name

    assert embedding_collection_name(provider, model) == expected


def test_settings_auto_qdrant_collection_follows_embedding() -> None:
    settings = Settings(
        _env_file=None,
        qdrant_collection="auto",
        embedding_provider="voyage",
        embedding_model="voyage-3-lite",
    )

    assert settings.resolved_qdrant_collection == "mathbird_voyage_voyage_3_lite"


def test_settings_explicit_qdrant_collection_override() -> None:
    settings = Settings(
        _env_file=None,
        qdrant_collection="my_fixed_collection",
        embedding_provider="voyage",
        embedding_model="voyage-3-lite",
    )

    assert settings.resolved_qdrant_collection == "my_fixed_collection"
