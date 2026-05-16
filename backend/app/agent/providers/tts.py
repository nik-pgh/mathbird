"""TTS provider factory."""

from __future__ import annotations

from livekit.agents import tts as tts_base

from app.config import Settings


def build_tts(settings: Settings) -> tts_base.TTS:
    name = settings.tts_provider
    if name == "cartesia":
        from livekit.plugins import cartesia

        return cartesia.TTS(
            model=settings.tts_model,
            voice=settings.tts_voice,
            api_key=settings.cartesia_api_key or None,
        )

    if name == "elevenlabs":
        from livekit.plugins import elevenlabs

        return elevenlabs.TTS(
            model=settings.tts_model,
            voice_id=settings.tts_voice,
            language=settings.tts_language,
            api_key=settings.eleven_api_key or None,
        )

    if name == "openai":
        from livekit.plugins import openai

        return openai.TTS(voice="alloy", api_key=settings.openai_api_key or None)

    raise ValueError(f"Unknown TTS provider: {name}")
