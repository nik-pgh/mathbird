"""Eager LiveKit plugin imports — must run on the main thread before console jobs."""

from __future__ import annotations

_plugins_loaded = False


def ensure_livekit_plugins_registered() -> None:
    """Import vendor plugin packages so ``Plugin.register_plugin`` runs on the main thread.

    ``console --text`` dispatches the entrypoint on a worker thread; lazy imports
    inside ``build_stt`` / ``build_llm`` / … then raise
    ``RuntimeError: Plugins must be registered on the main thread``.
    """
    global _plugins_loaded
    if _plugins_loaded:
        return

    # Import every plugin this repo's factories may use.
    from livekit.plugins import cartesia, deepgram, elevenlabs, openai, silero  # noqa: F401

    _plugins_loaded = True
