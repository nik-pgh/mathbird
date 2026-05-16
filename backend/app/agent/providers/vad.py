"""VAD provider factory."""

from __future__ import annotations

from livekit.agents import vad as vad_base

from app.config import Settings


def build_vad(settings: Settings) -> vad_base.VAD:
    name = settings.vad_provider
    if name == "silero":
        from livekit.plugins import silero

        return silero.VAD.load()

    raise ValueError(f"Unknown VAD provider: {name}")
