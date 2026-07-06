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
EmbeddingProvider = Literal[
    "openai", "cohere", "voyage", "google", "mistral", "jina", "huggingface"
]
RerankerProvider = Literal["none"]
RagIngestionMode = Literal["sync"]
RagPrefetchMode = Literal["null", "focus_change", "always"]
BoardReaderName = Literal["null", "openai_vision"]
BoardExtractorName = Literal["null", "openai"]
LegacyDocAccess = Literal["allow", "deny"]
GraderName = Literal["null", "openai"]


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
    llm_model: str = "gpt-4o"
    tts_model: str = "sonic-2"
    tts_voice: str = "794f9389-aac1-45b6-b726-9d9369183238"
    tts_language: str = ""

    # Max tokens per LLM turn. Voice sessions need short responses;
    # 150 caps a turn at ~3-5 sentences to prevent monologues.
    llm_max_tokens: int = 150

    # Provider API keys
    deepgram_api_key: str = ""
    openai_api_key: str = ""
    cartesia_api_key: str = ""
    eleven_api_key: str = ""

    # HTTP API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:5173"

    # Auth (Google OAuth)
    google_client_id: str = ""
    google_client_secret: str = ""
    auth_jwt_secret: str = ""
    auth_jwt_expiry_hours: int = 168
    oauth_redirect_url: str = "http://localhost:8000/api/auth/google/callback"
    auth_db_path: str = "./auth.db"
    auth_cookie_name: str = "mathbird_session"
    auth_cookie_secure: bool = False
    frontend_url: str = "http://localhost:5173"

    # Guest sessions — pre-indexed doc_id for "try without signup" flow.
    # Leave empty to disable guest mode. When set, unauthenticated token
    # requests fall back to this doc_id so the agent can search it.
    guest_sample_doc_id: str = ""

    # Pre-ownership uploads (no uploaded_by_user_id in meta.json). deny = invisible
    # except guest_sample_doc_id; allow = any authenticated user may access.
    legacy_doc_access: LegacyDocAccess = "deny"

    # Local script identity (``agent_console``, ``simulate_conversation.py``) when
    # no LiveKit participant metadata is available.
    sim_user_id: str = ""
    sim_active_doc_id: str = ""
    # When true (default), ``agent_console`` prompts for doc/user on stdin if
    # ``SIM_*`` are unset. Set false to skip prompts (non-TTY / automation).
    sim_interactive: bool = True

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
    rag_prefetch_mode: RagPrefetchMode = "focus_change"

    # LlamaParse / LlamaCloud
    llamaparse_api_key: str = ""
    llamaparse_tier: str = "agentic"
    llamaparse_version: str = "latest"

    # Qdrant — set QDRANT_COLLECTION=auto (default) to derive from embedding provider/model
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "auto"

    # Embeddings (see app/rag/embeddings.py — one collection per model/dimension)
    embedding_provider: EmbeddingProvider = "openai"
    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 8
    embedding_num_workers: int = 1
    embedding_requests_per_minute: int = 4
    cohere_api_key: str = ""
    voyage_api_key: str = ""
    google_api_key: str = ""
    mistral_api_key: str = ""
    jina_api_key: str = ""

    @property
    def resolved_qdrant_collection(self) -> str:
        """Qdrant collection for the active embedding pair.

        ``QDRANT_COLLECTION=auto`` (default) derives a stable slug from
        ``EMBEDDING_PROVIDER`` + ``EMBEDDING_MODEL``. Any other value is used
        as a fixed override (production deployments).
        """
        raw = self.qdrant_collection.strip()
        if not raw or raw.lower() == "auto":
            from app.rag.embeddings import embedding_collection_name

            return embedding_collection_name(self.embedding_provider, self.embedding_model)
        return raw

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
    board_reader_max_png_bytes: int = 1_048_576

    # PDF uploads
    max_upload_bytes: int = 50_000_000

    # AiBoard extractor — second LLM that watches the agent's spoken
    # sentences and publishes board items per sentence. Off by default.
    board_extractor: BoardExtractorName = "null"
    board_extractor_model: str = "gpt-4o-mini"
    board_extractor_timeout_seconds: float = 4.0
    board_extractor_queue_size: int = 20

    # Student-model grader — a second LLM that assesses each student turn and
    # updates mastery levels / misconceptions, so the student model evolves
    # every turn without relying on the main LLM calling progress tools. Off
    # by default; opt in with GRADER=openai.
    grader: GraderName = "null"
    grader_model: str = "gpt-4o-mini"
    grader_timeout_seconds: float = 5.0

    # Observability (Arize Phoenix LLM/RAG tracing). Off by default. To enable,
    # set ``PHOENIX_ENABLED=true``; for local UI run ``uv run phoenix serve``.
    phoenix_enabled: bool = False
    phoenix_project: str = "mathbird"
    # Phoenix Cloud: use the space hostname from Settings, e.g.
    # ``https://app.phoenix.arize.com/s/<space-name>``. Empty = local default.
    phoenix_endpoint: str = ""
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
