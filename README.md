# mathbird

A LiveKit voice agent with a configurable STT/LLM/TTS/VAD pipeline and a React
frontend for uploading PDFs that the agent can reason over.

Deployed to **LiveKit Cloud**. RAG is provider-driven: the default no-op
retriever keeps local setup simple, and the built-in LlamaParse + LlamaIndex +
Qdrant provider can parse, index, and retrieve from uploaded textbooks.

## Architecture

```
mathbird/
├── backend/                       # Python: LiveKit agent worker + FastAPI HTTP API
│   └── app/
│       ├── config.py              # all env-driven settings (single source of truth)
│       ├── agent/
│       │   ├── main.py            # LiveKit worker entrypoint — joins rooms
│       │   ├── tools.py           # function tools the LLM can call (incl. RAG search)
│       │   └── providers/         # swappable STT / LLM / TTS / VAD factories
│       ├── api/
│       │   ├── main.py            # FastAPI app
│       │   └── routes/
│       │       ├── token.py       # POST /api/token       → LiveKit access token
│       │       └── documents.py   # POST /api/documents   → PDF upload
│       ├── storage/               # local-disk + S3 backends behind a Protocol
│       └── rag/                   # Retriever Protocol + null and Qdrant providers
└── frontend/                      # Vite + React + TypeScript
    └── src/
        ├── pages/
        │   ├── UploadPage.tsx     # landing page: PDF dropzone
        │   └── VoiceAgentPage.tsx # LiveKit room + voice assistant UI
        ├── components/
        │   └── PdfDropZone.tsx
        └── lib/api.ts             # typed client for the backend
```

### How a conversation flows

```
  ┌──────────────┐   1. POST /api/token        ┌─────────────────────┐
  │  React app   │ ─────────────────────────▶ │  FastAPI (backend)  │
  │              │   2. token + room name      │                     │
  │              │ ◀───────────────────────── │                     │
  └──────┬───────┘                             └─────────────────────┘
         │ 3. connect with token
         ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                       LiveKit Cloud (room)                      │
  └────────────┬────────────────────────────────────────┬───────────┘
               │ 4. participant joined event             │
               ▼                                         │
  ┌─────────────────────────┐                           │
  │ LiveKit agent worker    │  ◀── audio frames ──────  │
  │ (Python, app/agent)     │                           │
  │  STT → LLM → TTS        │  ── audio frames ──────▶  │
  │  ↑ function_tool:       │                           │
  │    search_documents() ──┼─► NullRetriever by default│
  │                         │    or Qdrant RAG provider │
  └─────────────────────────┘                           ▼
```

### What's a LiveKit "room"?

LiveKit organizes real-time audio/video into **rooms** — short-lived,
named channels. Anyone with a JWT scoped to a given room name can join it and
send/receive media to/from other participants.

In this app:

1. The user clicks "Start conversation" on the frontend.
2. The frontend asks the backend for a JWT (`POST /api/token`). The backend
   signs it with the LiveKit Cloud API key/secret and returns it along with
   the room name (a random ID by default).
3. The frontend connects to LiveKit Cloud and joins that room.
4. The agent worker is registered with LiveKit Cloud as a *worker*. When a
   participant joins a room, LiveKit dispatches the worker into that room.
5. The worker streams audio out of the room into STT, pushes transcripts into
   the LLM, streams the LLM's response into TTS, and sends synthesized audio
   back into the room.

You don't run a LiveKit server yourself — LiveKit Cloud handles the SFU.

## Quick start

### 1. Sign up + get credentials

* Create a project at https://cloud.livekit.io
* Grab the URL, API key, and API secret from **Settings → Keys**
* Sign up for the provider keys you'll use:
  * Deepgram: https://console.deepgram.com
  * OpenAI: https://platform.openai.com
  * Cartesia: https://play.cartesia.ai

### 2. Configure env

```bash
cp .env.example .env
# Edit .env, fill in LIVEKIT_* and the provider keys for your selected stack
```

The frontend reads its own `.env.local`:

```bash
cp frontend/.env.example frontend/.env.local
# Set VITE_API_BASE_URL and VITE_LIVEKIT_URL
```

### 3. Install + run (three terminals)

**Backend HTTP API** (PDF uploads + LiveKit tokens):

```bash
cd backend
uv sync                         # or: python -m venv .venv && pip install -e ".[dev]"
uv run uvicorn app.api.main:app --reload --port 8000
```

**LiveKit agent worker** (joins rooms, runs the voice pipeline):

```bash
cd backend
uv run python -m app.agent.main dev
```

**Frontend**:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, drop a PDF on the landing page, click "Talk to
the agent →", and start speaking.

## Swapping providers

All four modalities are env-driven. To change a vendor, edit `.env`:

```bash
STT_PROVIDER=deepgram    # deepgram | openai
LLM_PROVIDER=openai      # openai
TTS_PROVIDER=cartesia    # cartesia | openai
VAD_PROVIDER=silero      # silero
```

To add a new vendor (e.g., ElevenLabs TTS):

1. Add the plugin to `backend/pyproject.toml`.
2. Add a branch in `backend/app/agent/providers/tts.py`.
3. Add the new option to `TtsProvider` in `backend/app/config.py`.

The agent code is unchanged.

## RAG with LlamaParse + Qdrant

`backend/app/rag/retriever.py` defines a `Retriever` protocol:

```python
class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 4,
        doc_ids: tuple[str, ...] = (),
    ) -> list[RetrievedChunk]: ...
    async def ingest_pdf(self, path: str, *, doc_id: str) -> None: ...
```

The PDF upload route calls `ingest_pdf` after storing the file. In v1 ingestion
runs synchronously during upload; if ingestion fails, the route attempts to
delete the stored PDF and returns an upload error. The agent's `search_documents`
function tool calls `retrieve` whenever the LLM decides it needs to look
something up, and can pass a document id when the active UI/session knows which
textbook the user is asking about.

By default `RAG_PROVIDER=null` selects `NullRetriever`, so `ingest_pdf` and
`retrieve` are no-ops and the app runs without RAG infrastructure. To enable
the built-in textbook RAG provider, set:

```bash
RAG_PROVIDER=llamaindex_qdrant
LLAMAPARSE_API_KEY=...
OPENAI_API_KEY=...
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=mathbird_documents
```

With `RAG_PROVIDER=llamaindex_qdrant`, uploads are parsed with LlamaParse,
normalized and indexed through LlamaIndex into Qdrant, and
`search_documents` returns cited chunks from that collection.

For local Qdrant:

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

## Switching PDF storage to S3

Set `STORAGE_BACKEND=s3` plus the `S3_*` and `AWS_*` env vars. The local
implementation and the S3 implementation share the same `StorageBackend`
interface, so no other code changes are needed.

## Project conventions

* **No vendor lock-in in business code.** The agent never imports `deepgram`
  / `openai` / `cartesia` / `chroma` directly. Everything goes through the
  provider / storage / retriever interfaces.
* **One env var per knob.** All config flows through `app.config.Settings`.
  Don't read `os.environ` elsewhere.
* **Add a new provider / backend by adding a branch + a literal type.** Never
  by editing call sites.
