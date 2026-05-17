# Architecture

Deeper-dive companion to [`../CLAUDE.md`](../CLAUDE.md). Read CLAUDE.md first — it has the rules and the "where to add things" table. This file explains the *why* and the *how*.

## Two backend processes, one Python package

`backend/app/` is imported by two long-running processes that share `app.config.Settings` but otherwise do different jobs:

| Process | Entry | What it does | When it runs |
| --- | --- | --- | --- |
| **LiveKit agent worker** | `python -m app.agent.main dev` | Registers as a LiveKit worker against LiveKit Cloud. When a participant joins any room scoped to this worker's API key, LiveKit dispatches `entrypoint(ctx)` into that room. The worker streams audio in, runs STT→LLM→TTS, streams audio back. | Always running. One worker process can handle many concurrent rooms. |
| **HTTP API** | `uvicorn app.api.main:app` | FastAPI. Issues LiveKit JWTs and accepts PDF uploads. Stateless besides the `lru_cache`d singletons. | Always running. |

Both processes call `get_settings()`, `get_storage()`, and `get_retriever()` — all `lru_cache`d / module-level singletons. The two processes are independent OS processes; their caches don't share state.

## How a voice conversation flows

```
  Frontend (React)                Backend HTTP API           LiveKit Cloud (SFU)         Agent Worker (Python)
  ─────────────────              ──────────────────         ────────────────────         ─────────────────────
        │                                │                            │                            │
        │ 1. POST /api/token             │                            │                            │
        │ ─────────────────────────────▶ │                            │                            │
        │                                │  sign JWT with             │                            │
        │                                │  LIVEKIT_API_SECRET        │                            │
        │ 2. {token, url, room}          │                            │                            │
        │ ◀───────────────────────────── │                            │                            │
        │                                                                                          │
        │ 3. WebRTC connect (with JWT)                                                             │
        │ ────────────────────────────────────────────────────────▶  │                            │
        │                                                              │                            │
        │                                                              │ 4. participant joined       │
        │                                                              │ ──────────────────────────▶│
        │                                                              │ 5. dispatch entrypoint     │
        │                                                              │                            │
        │ ◀── audio frames ───────────────────────────────────────── ╳ ──────── audio frames ────▶│
        │                                                              │                            │ STT
        │                                                              │                            │  ↓
        │                                                              │                            │ LLM ──▶ search_documents(query)
        │                                                              │                            │  ↓             │
        │                                                              │                            │ TTS            ▼
        │                                                              │                            │       Retriever.retrieve(...)
        │ ◀── audio frames ───────────────────────────────────────── ╳ ◀──────── audio frames ─────│       (NullRetriever by default;
        │                                                                                          │        llamaindex_qdrant for real RAG)
```

Key points:

- **No self-hosted SFU.** LiveKit Cloud terminates the WebRTC connection. We never see raw RTP — we use the LiveKit Agents SDK.
- **The worker is a long-lived client**, not an HTTP server. It "registers" against the cloud using API key/secret and waits for room-join events.
- **Function tools are mid-conversation callbacks.** When the LLM emits a tool call, the LiveKit Agents framework dispatches it to the matching `@function_tool`-decorated function in `app.agent.tools` and inserts the result back into the LLM's context. Today's tools are `search_documents` (RAG) plus three whiteboard tools (`update_ai_board`, `clear_ai_board`, `read_user_board`).
- **The HTTP API and the worker don't talk to each other directly.** Their only shared state is `Settings` (env-driven) and whatever the active `Retriever`/`StorageBackend` implementations happen to persist (filesystem, S3, vector store, ...).
- **Whiteboard traffic rides on the same LiveKit room as the audio**, but on two named data-channel topics (`ai_board` server→clients, `user_board` clients→server). The HTTP API is never in this path either.

## The five swappable seams

Each seam is a Protocol (or LiveKit base type) + a factory + a `Literal` in `Settings`. Adding a new option means touching exactly three places: the factory, the Literal, and `pyproject.toml`. No call site changes.

### 1. STT / LLM / TTS / VAD providers

- **Protocol:** LiveKit Agents' own base classes (`stt_base.STT`, `llm_base.LLM`, `tts_base.TTS`, `vad_base.VAD`).
- **Factory:** `backend/app/agent/providers/{stt,llm,tts,vad}.py` — each file is one function (`build_*`) with an `if name == "...":` chain.
- **Literal:** `SttProvider`, `LlmProvider`, `TtsProvider`, `VadProvider` in `app/config.py`.
- **Wired up at:** `app/agent/main.py::entrypoint` builds them and hands them to `AgentSession(...)`.

The factories import vendor plugins **lazily** inside the branch, so installing a plugin you don't use doesn't slow startup.

### 2. Storage backends (`StorageBackend`)

- **Protocol:** `app/storage/base.py::StorageBackend` (`put` / `open` / `list` / `delete`, all async).
- **Factory:** `app/storage/base.py::get_storage()`, cached.
- **Literal:** `StorageBackendName` in `app/config.py`.
- **Implementations:** `local.py` (filesystem, with path-traversal defense) and `s3.py` (boto3).

`StoredObject.uri` is a `file://` URI for local and `s3://` for S3 — that's how the upload route knows what to hand to the retriever.

### 3. Retriever (`Retriever`)

- **Protocol:** `app/rag/retriever.py::Retriever` (`retrieve(query, top_k, doc_ids=...)` and `ingest_pdf(path, doc_id)`, both async).
- **Factory:** `app/rag/retriever.py::get_retriever()`, module-level singleton.
- **Implementations:** `NullRetriever` for the default `RAG_PROVIDER=null` path, and `LlamaIndexQdrantRetriever` via `RAG_PROVIDER=llamaindex_qdrant`.

`ingest_pdf` is called by the upload route after `storage.put`. In v1 this happens synchronously inside the upload request; if ingestion fails, the route attempts to delete the stored PDF and returns an error instead of listing an unindexed document. `retrieve` is called by the `search_documents` function tool during a conversation and can be scoped to a specific document id when the caller has one. With the default null provider both methods are no-ops, so the system runs end-to-end without RAG infrastructure. With `RAG_PROVIDER=llamaindex_qdrant`, PDF uploads are parsed with LlamaParse, normalized and indexed through LlamaIndex into Qdrant, and searches retrieve cited textbook chunks from that collection.

### 4. Function tools (the LLM's API into our code)

- **Where:** `app/agent/tools.py`. Decorate with `@function_tool`, return from `build_function_tools()`.
- **The LLM sees only:** the function name, parameter types, and docstring. Write docstrings deliberately — they're effectively system-prompt extensions.
- **Today's set:** `search_documents` (RAG seam), `update_ai_board` / `clear_ai_board` (publish on the `ai_board` data topic), `read_user_board` (reads cached `BoardState`).

### 5. Board reader (`BoardReader`)

- **Protocol:** `app/agent/whiteboard/reader/__init__.py::BoardReader` — `interpret(png_bytes: bytes) -> str`.
- **Factory:** `app/agent/whiteboard/reader/__init__.py::get_board_reader()`, `lru_cache`d.
- **Literal:** `BoardReaderName` in `app/config.py` (`null | openai_vision`).
- **Implementations:** `NullBoardReader` (default, returns nothing) and `OpenAIVisionBoardReader` (vision-LLM handwriting recognition, configurable model + API key).

The reader is invoked by the debounced `install_user_board_listener` pipeline in `app/agent/whiteboard/listener.py`. Its output lands in a per-room `BoardState`, and `WhiteboardAgent.on_user_turn_completed` injects that text as a synthetic system message at the start of every LLM turn — keeping the agent up to date on what the student has written without polluting the persistent `Agent.chat_ctx`.

## Frontend ↔ backend boundary

Two contracts, both hand-mirrored.

**REST** — `frontend/src/lib/api.ts` is the only place in the frontend that calls `fetch()`. Everything else imports the typed wrapper. Three calls:

| Call | Backend route | Returns |
| --- | --- | --- |
| `requestToken({identity?, room?, name?})` | `POST /api/token` | `{token, url, room, identity}` |
| `uploadPdf(file)` | `POST /api/documents` (multipart) | `UploadedDocument` |
| `listDocuments()` | `GET /api/documents` | `UploadedDocument[]` |

Then the React app connects to LiveKit Cloud directly via `@livekit/components-react` (`<LiveKitRoom serverUrl={url} token={token} />`) — the backend is no longer in the audio path.

**LiveKit data channel** — schemas live in `backend/app/agent/whiteboard/messages.py` (pydantic) and are mirrored in `frontend/src/lib/whiteboard.ts` (plus `encode*` / `decode*` helpers). Two named topics:

| Topic | Direction | Payload |
| --- | --- | --- |
| `ai_board` | server → clients | `AiBoardUpdate` — `op: "upsert" \| "clear"` with discriminated `AiBoardText \| AiBoardPlot \| AiBoardShape` items. |
| `user_board` | clients → server | `UserBoardSnapshot` — base64 PNG (≤512px long edge) + `captured_at_ms` + `is_empty`. |

There is no codegen — change both sides together.

Voice UI is composed from LiveKit React primitives:
- `useVoiceAssistant()` — agent state + audio track + agent transcriptions
- `useTrackTranscription()` — user's mic transcription (via LiveKit's STT relay)
- `useDataChannel(topic)` — wrapped in `useBoardChannel` for typed `ai_board` / `user_board` traffic
- `<BarVisualizer />` — audio reactive bars
- `<RoomAudioRenderer />` — actually plays the agent's audio

## Env-driven configuration

`app.config.Settings` (pydantic-settings) reads `.env` and `../.env`. Backend code uses `get_settings()` everywhere; **never** `os.environ`. The frontend has its own `frontend/.env.local` with `VITE_*` prefixes (Vite requirement).

When introducing a new knob:
1. Add a field on `Settings` with a sensible default.
2. Document it in `.env.example` with an inline comment about valid values.
3. Read it via `get_settings()`.
