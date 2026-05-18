"""Centralized settings. Anything env-driven flows through this module."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PERSONA_FILE = _BACKEND_DIR / "personas" / "default.yaml"

SttProvider = Literal["deepgram", "openai"]
LlmProvider = Literal["openai"]
TtsProvider = Literal["cartesia", "elevenlabs", "openai"]
VadProvider = Literal["silero"]
StorageBackendName = Literal["local", "s3"]
RagProvider = Literal["null", "llamaindex_qdrant"]
ParserProvider = Literal["llamaparse"]
RerankerProvider = Literal["none"]
RagIngestionMode = Literal["sync"]
BoardReaderName = Literal["null", "openai_vision"]
BoardExtractorName = Literal["null", "openai"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LiveKit Cloud
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""

    # Provider selection
    stt_provider: SttProvider = "deepgram"
    llm_provider: LlmProvider = "openai"
    tts_provider: TtsProvider = "cartesia"
    vad_provider: VadProvider = "silero"

    # Per-provider model overrides (empty = use plugin default)
    stt_model: str = "nova-3"
    llm_model: str = "gpt-4o-mini"
    tts_model: str = "sonic-2"
    tts_voice: str = "794f9389-aac1-45b6-b726-9d9369183238"
    tts_language: str = "ko"

    # Provider API keys
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    cartesia_api_key: str = ""
    eleven_api_key: str = ""

    # HTTP API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:5173"

    # Storage
    storage_backend: StorageBackendName = "local"
    storage_local_dir: str = "./uploads"
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # RAG
    rag_provider: RagProvider = "null"
    parser_provider: ParserProvider = "llamaparse"
    reranker_provider: RerankerProvider = "none"
    rag_ingestion_mode: RagIngestionMode = "sync"
    rag_top_k: int = 4

    # LlamaParse / LlamaCloud
    llamaparse_api_key: str = ""
    llamaparse_tier: str = "agentic"
    llamaparse_version: str = "latest"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "mathbird_documents"

    # Embeddings
    embedding_model: str = "text-embedding-3-small"

    # Agent persona — system prompt is loaded from a YAML file so it can be
    # edited without touching code or env vars. Point PERSONA_FILE at a
    # different file to swap personas per deployment.
    persona_file: Path = Field(default=DEFAULT_PERSONA_FILE)

    @property
    def agent_instructions(self) -> str:
        return _load_persona(self.persona_file)

    # Whiteboards
    board_reader: BoardReaderName = "null"
    board_reader_model: str = "gpt-4o-mini"
    board_reader_interval_seconds: float = 2.0
    board_reader_max_image_dim: int = 512

    # AiBoard extractor — second LLM that watches the agent's spoken
    # sentences and publishes board items per sentence. Off by default.
    board_extractor: BoardExtractorName = "null"
    board_extractor_model: str = "gpt-4o-mini"
    board_extractor_timeout_seconds: float = 2.0

    # Observability (Arize Phoenix LLM/RAG tracing). Off by default. To enable:
    # install with ``uv sync --extra observability``, run ``phoenix serve`` in
    # another shell, then set ``PHOENIX_ENABLED=true``.
    phoenix_enabled: bool = False
    phoenix_project: str = "mathbird"
    phoenix_endpoint: str = ""  # empty = phoenix auto-detect (gRPC :4317 or HTTP :6006)
    # API key for Phoenix Cloud (app.phoenix.arize.com). Phoenix turns this
    # into an ``Authorization: Bearer …`` header. Empty for local Phoenix.
    phoenix_api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def _load_persona(persona_file: Path) -> str:
    data = yaml.safe_load(persona_file.read_text(encoding="utf-8"))
    instructions = data.get("instructions") if isinstance(data, dict) else None
    if not isinstance(instructions, str) or not instructions.strip():
        raise ValueError(
            f"Persona file {persona_file} must define a non-empty 'instructions' string."
        )
    return instructions
