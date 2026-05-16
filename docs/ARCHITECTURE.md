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
        │ ◀── audio frames ───────────────────────────────────────── ╳ ◀──────── audio frames ─────│       (NullRetriever today)
```

Key points:

- **No self-hosted SFU.** LiveKit Cloud terminates the WebRTC connection. We never see raw RTP — we use the LiveKit Agents SDK.
- **The worker is a long-lived client**, not an HTTP server. It "registers" against the cloud using API key/secret and waits for room-join events.
- **Function tools are mid-conversation callbacks.** When the LLM emits a tool call, the LiveKit Agents framework dispatches it to the matching `@function_tool`-decorated function in `app.agent.tools` and inserts the result back into the LLM's context.
- **The HTTP API and the worker don't talk to each other directly.** Their only shared state is `Settings` (env-driven) and whatever the active `Retriever`/`StorageBackend` implementations happen to persist (filesystem, S3, vector store, ...).

## The four swappable seams

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

- **Protocol:** `app/rag/retriever.py::Retriever` (`retrieve(query, top_k)` and `ingest_pdf(path, doc_id)`, both async).
- **Factory:** `app/rag/retriever.py::get_retriever()`, module-level singleton.
- **Implementations:** `NullRetriever` only. To add LlamaIndex/LangChain/etc., add a module under `app/rag/` and return it from `get_retriever()`.

`ingest_pdf` is called by the upload route after `storage.put`. `retrieve` is called by the `search_documents` function tool during a conversation. Both are no-ops today, so the system runs end-to-end without a vector store.

### 4. Function tools (the LLM's API into our code)

- **Where:** `app/agent/tools.py`. Decorate with `@function_tool`, return from `build_function_tools()`.
- **The LLM sees only:** the function name, parameter types, and docstring. Write docstrings deliberately — they're effectively system-prompt extensions.

## Frontend ↔ backend boundary

`frontend/src/lib/api.ts` is the only place in the frontend that calls `fetch()`. Everything else imports the typed wrapper. Three calls:

| Call | Backend route | Returns |
| --- | --- | --- |
| `requestToken({identity?, room?, name?})` | `POST /api/token` | `{token, url, room, identity}` |
| `uploadPdf(file)` | `POST /api/documents` (multipart) | `UploadedDocument` |
| `listDocuments()` | `GET /api/documents` | `UploadedDocument[]` |

Then the React app connects to LiveKit Cloud directly via `@livekit/components-react` (`<LiveKitRoom serverUrl={url} token={token} />`) — the backend is no longer in the audio path.

Voice UI is composed from LiveKit React primitives:
- `useVoiceAssistant()` — agent state + audio track + agent transcriptions
- `useTrackTranscription()` — user's mic transcription (via LiveKit's STT relay)
- `<BarVisualizer />` — audio reactive bars
- `<RoomAudioRenderer />` — actually plays the agent's audio

## Env-driven configuration

`app.config.Settings` (pydantic-settings) reads `.env` and `../.env`. Backend code uses `get_settings()` everywhere; **never** `os.environ`. The frontend has its own `frontend/.env.local` with `VITE_*` prefixes (Vite requirement).

When introducing a new knob:
1. Add a field on `Settings` with a sensible default.
2. Document it in `.env.example` with an inline comment about valid values.
3. Read it via `get_settings()`.

