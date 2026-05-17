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
TTS_PROVIDER=cartesia    # cartesia | elevenlabs | openai
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

## Whiteboards

`app/agent/whiteboard/` is a pluggable handwriting-recognition + per-room state
surface that runs alongside the voice pipeline. On every room join, the
entrypoint installs a `user_board` data-channel listener and attaches a
`BoardState` to `AgentSession.userdata`; a `WhiteboardAgent` subclass then
injects the latest student-board reading into the LLM's chat context per turn.
The LLM publishes back via the `update_ai_board` / `clear_ai_board` /
`read_user_board` function tools.

Default `BOARD_READER=null` keeps the reader a no-op; enable real OCR with:

```bash
BOARD_READER=openai_vision         # null | openai_vision
BOARD_READER_MODEL=gpt-4o-mini
BOARD_READER_INTERVAL_SECONDS=2.0  # debounce window
BOARD_READER_MAX_IMAGE_DIM=512     # client-side resize hint
OPENAI_API_KEY=...
```

Wire schemas live in `app/agent/whiteboard/messages.py` and are mirrored in
`frontend/src/lib/whiteboard.ts`. There is no schema generator; change both
sides together.

## Observability — Arize Phoenix (optional)

When you need to see, per voice turn, exactly which `query` the LLM passed
to `search_documents`, which chunks Qdrant returned with what similarity
scores, and how long each pipeline stage took, turn on Phoenix tracing.

Install the optional dep group and start the Phoenix UI:

```bash
cd backend
uv sync --extra observability
uv run phoenix serve            # opens http://localhost:6006
```

Add these env vars (off by default — production stays untouched):

```bash
# Backend observability (Arize Phoenix)
PHOENIX_ENABLED=true
PHOENIX_PROJECT=mathbird
PHOENIX_ENDPOINT=                 # blank = phoenix default (gRPC :4317 / UI on :6006)
```

Restart **both** backend processes — `get_settings()` and the
instrumentation patch are per-process. Once both are up:

- Every OpenAI LLM completion is captured (system + user messages, tool
  calls with arguments, token usage, latency).
- Every `Retriever.retrieve()` is captured with the query, returned
  chunks, similarity scores, and metadata — same shot as `probe_retrieval`
  but live for every real turn.
- Every `@function_tool` call shows up as a child span of its parent LLM
  call.

The instrumentation lives in `app/observability.py` (one module, vendor
imports lazy and confined). Setting `PHOENIX_ENABLED=false` (or leaving
it unset) makes `setup_phoenix()` a no-op — no Phoenix imports at all.
