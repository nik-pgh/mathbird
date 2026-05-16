# mathbird backend

Two processes live here:

| Process | Module | Purpose |
| --- | --- | --- |
| LiveKit agent worker | `app.agent.main` | Joins LiveKit rooms, runs the STT→LLM→TTS pipeline |
| HTTP API | `app.api.main:app` | Issues LiveKit access tokens + accepts PDF uploads |

Both share `app.config.Settings` and the storage / RAG abstractions.

## Setup

```bash
cd backend
uv sync              # or: pip install -e ".[dev]"
cp ../.env.example ../.env   # fill in LIVEKIT_* and provider keys
```

## Run

```bash
# Terminal 1 — HTTP API
uv run uvicorn app.api.main:app --reload --port 8000

# Terminal 2 — LiveKit agent worker (connects to LiveKit Cloud)
uv run python -m app.agent.main dev
```

## Swapping providers

Edit `.env` — no code changes required:

```bash
STT_PROVIDER=deepgram    # deepgram | openai
LLM_PROVIDER=openai      # openai
TTS_PROVIDER=cartesia    # cartesia | openai
VAD_PROVIDER=silero      # silero
```

To add a new vendor (e.g., ElevenLabs TTS), add a branch in
`app/agent/providers/tts.py` and a new option in `app.config.TtsProvider`.
Nothing else changes.

## RAG with LlamaParse + Qdrant

`app/rag/retriever.py` defines the `Retriever` protocol with `retrieve(...)` and
`ingest_pdf(...)`. The default `RAG_PROVIDER=null` keeps the no-op retriever.

To enable math textbook RAG, set:

```bash
RAG_PROVIDER=llamaindex_qdrant
LLAMAPARSE_API_KEY=...
OPENAI_API_KEY=...
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=mathbird_documents
```

For local Qdrant, run:

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

Then upload a PDF through `POST /api/documents`; the v1 upload route stores the PDF and
calls the active retriever's `ingest_pdf` synchronously. If ingestion fails, the route
attempts to delete the stored PDF and returns an upload error rather than listing an
unindexed document. A background job queue can replace this call site later without
changing the retriever interface.
