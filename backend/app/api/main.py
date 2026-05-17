"""FastAPI app: serves the LiveKit token and PDF upload endpoints.

Run locally:
    uv run uvicorn app.api.main:app --reload --port 8000
"""

from __future__ import annotations

# Phoenix instrumentation must patch OpenAI / LlamaIndex client classes
# before any module that uses them is imported. ``.routes.documents``
# pulls in ``app.rag`` which imports LlamaIndex at module load, so the
# patch has to happen first.
from app.observability import setup_phoenix

setup_phoenix()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.config import get_settings  # noqa: E402

from .routes import documents, token  # noqa: E402

settings = get_settings()

app = FastAPI(title="mathbird API", version="0.1.0")

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
