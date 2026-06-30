"""Factories that build LiveKit Agents provider components from settings.

Each modality (STT / LLM / TTS / VAD) has its own factory module so adding a
new vendor only touches one file. The agent code in ``main.py`` only sees the
factory output — it never imports vendor plugins directly.
"""

from .llm import build_llm
from .register import ensure_livekit_plugins_registered
from .stt import build_stt
from .tts import build_tts
from .vad import build_vad

__all__ = ["build_llm", "build_stt", "build_tts", "build_vad", "ensure_livekit_plugins_registered"]
