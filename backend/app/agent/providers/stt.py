"""STT provider factory."""

from __future__ import annotations

from livekit.agents import stt as stt_base

from app.config import Settings


def build_stt(settings: Settings) -> stt_base.STT:
    name = settings.stt_provider
    if name == "deepgram":
        from livekit.plugins import deepgram

        return deepgram.STT(model=settings.stt_model, api_key=settings.deepgram_api_key or None)

    if name == "openai":
        from livekit.plugins import openai

        return openai.STT(model="whisper-1", api_key=settings.openai_api_key or None)

    raise ValueError(f"Unknown STT provider: {name}")
