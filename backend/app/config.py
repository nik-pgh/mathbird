"""Centralized settings. Anything env-driven flows through this module."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SttProvider = Literal["deepgram", "openai"]
LlmProvider = Literal["openai"]
TtsProvider = Literal["cartesia", "elevenlabs", "openai"]
VadProvider = Literal["silero"]
StorageBackendName = Literal["local", "s3"]
BoardReaderName = Literal["null", "openai_vision"]


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

    # Agent persona / system prompt — kept here so it's swappable per deployment.
    agent_instructions: str = Field(
        default=(
            "You are a helpful voice assistant. Keep responses concise and "
            "conversational. If the user asks about a document, use the "
            "retrieval tool to ground your answer."
        ),
    )

    # Whiteboards
    board_reader: BoardReaderName = "null"
    board_reader_model: str = "gpt-4o-mini"
    board_reader_interval_seconds: float = 2.0
    board_reader_max_image_dim: int = 512

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
