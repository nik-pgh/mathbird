"""FastAPI app: serves the LiveKit token and PDF upload endpoints.

Run locally:
    uv run uvicorn app.api.main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.observability import setup_phoenix

from .routes import documents, token

settings = get_settings()


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Start uvicorn listening immediately; patch Phoenix in the background.

    Import-time ``setup_phoenix()`` added ~15s before bind on Fly cold starts,
    which tripped health checks (502) even though the process was healthy.
    """
    phoenix_task: asyncio.Task[None] | None = None
    if settings.phoenix_enabled:
        phoenix_task = asyncio.create_task(asyncio.to_thread(setup_phoenix))
    yield
    if phoenix_task is not None:
        await phoenix_task


app = FastAPI(title="mathbird API", version="0.1.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(token.router, prefix="/api", tags=["livekit"])
app.include_router(documents.router, prefix="/api", tags=["documents"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
