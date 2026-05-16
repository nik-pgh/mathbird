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

## Plugging in RAG later

`app/rag/retriever.py` defines a `Retriever` protocol with two methods:
`retrieve(query)` and `ingest_pdf(path, doc_id)`. Today `NullRetriever`
returns nothing. When you pick a framework (LlamaIndex, LangChain, OpenAI File
Search, …):

1. Add a new module under `app/rag/` implementing the protocol.
2. Return it from `app/rag/retriever.py::get_retriever()`.

The upload route and the agent's `search_documents` tool will start working
immediately — neither needs to change.
