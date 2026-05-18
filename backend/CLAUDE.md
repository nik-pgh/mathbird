# CLAUDE.md — backend

Scoped guidance for `backend/`. The root [`../CLAUDE.md`](../CLAUDE.md) has the cross-cutting rules; this file is the backend-only quick reference. For deeper architecture see [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).

## Two processes share this package

| Process | Run | What it does |
| --- | --- | --- |
| HTTP API | `uv run uvicorn app.api.main:app --reload --port 8000` | Signs LiveKit JWTs (`POST /api/token`), accepts PDF uploads (`POST /api/documents`). |
| Agent worker | `uv run python -m app.agent.main dev` | Registers as a LiveKit worker; joins rooms; runs STT→LLM→TTS pipeline. |

Both processes import `app.config.get_settings()` and the storage / RAG accessors. They're separate OS processes with separate `lru_cache`d singletons.

## Commands

```bash
cd backend
uv sync                              # install
uv run ruff check .                  # lint
uv run ruff format .                 # format
uv run pytest                        # tests (asyncio auto-mode)
uv run pytest path::test_name        # single test
```

Python 3.11+. Ruff line length 100, selecting `E, F, I, UP, B`.

## Rules specific to this package

1. **All env vars go through `app.config.Settings`.** Never `os.environ.get(...)` outside `config.py`. Add the field with a default, then `get_settings().my_field`.
2. **Provider/storage/retriever/board-reader choices are `Literal` types.** Adding a new option = add to the Literal + add a branch in the factory + add the dep. Never modify call sites.
3. **Vendor SDKs stay isolated to provider boundaries.** `from livekit.plugins import deepgram` lives in `app/agent/providers/stt.py` and not in business code. Same rule for `openai`, `cartesia`, `elevenlabs`, `boto3`, LlamaIndex, Qdrant, etc.: keep vendor imports inside agent provider modules, storage modules, RAG implementation modules under `app/rag/`, and board-reader modules under `app/agent/whiteboard/reader/`. Lazy imports keep startup fast and let users skip plugins they don't need.
4. **Function tools are the agent's API surface.** New LLM-callable capabilities = a new `@function_tool` async function in `app/agent/tools.py`, returned from `build_function_tools()`. The agent picks it up automatically. **Write the docstring carefully** — the LLM reads it. Current LLM-facing tools: `search_documents` (RAG) + `read_user_board` (student board reading). AiBoard writes are NOT done by the LLM — they come from the per-sentence `BoardExtractor` in `app/agent/whiteboard/extractor/` watching the agent's transcription stream.
5. **`Settings` reads `.env` AND `../.env`.** The repo-root `.env` is the canonical location for shared secrets. `backend/README.md` says `cp ../.env.example ../.env`.
6. **Singletons are cached.** `get_settings()`, `get_storage()`, `get_retriever()`, and `get_board_reader()` are all `lru_cache` or module-level. Restart the process to pick up env changes; clear caches in tests.
7. **Whiteboard wire format is mirrored by hand.** Pydantic schemas in `app/agent/whiteboard/messages.py` are mirrored in `frontend/src/lib/whiteboard.ts`. No codegen — update both sides in the same change.

## Quick "where to add..." map

| Task | File(s) |
| --- | --- |
| New STT/LLM/TTS/VAD vendor | `app/agent/providers/<modality>.py` + `Literal` in `config.py` + dep in `pyproject.toml` |
| New LLM capability | `app/agent/tools.py` (new `@function_tool`, add to `build_function_tools`) |
| Built-in RAG implementation | Set `RAG_PROVIDER=llamaindex_qdrant`; add a new module under `app/rag/` only for another provider. |
| New HTTP endpoint | New file in `app/api/routes/`, mount in `app/api/main.py` |
| New storage backend | New file in `app/storage/` implementing `StorageBackend`; branch in `get_storage()` + `Literal` |
| New whiteboard item kind | Pydantic model in `app/agent/whiteboard/messages.py`, extend `AiBoardItem`; mirror in `frontend/src/lib/whiteboard.ts`; render in `BoardItem.tsx` |
| New board reader (handwriting recognizer) | New module under `app/agent/whiteboard/reader/`, add to `BoardReaderName`, branch in `get_board_reader()` |
| New board extractor (sentence-streaming AiBoard writer) | New module under `app/agent/whiteboard/extractor/` implementing `BoardExtractor`; branch in `get_board_extractor()` + `Literal` in `BoardExtractorName` |
| New env var | Field on `Settings` in `app/config.py` + entry in `../.env.example` |
| Tune agent persona | Edit `backend/personas/default.yaml`, or set `PERSONA_FILE` to another YAML; `Settings.agent_instructions` loads it via `_load_persona` |
| Add observability (LLM/RAG tracing) | Already wired via `app/observability.py`; toggle with `PHOENIX_ENABLED=true` after `uv sync --extra observability` |

## Gotchas

- `LIVEKIT_*` env vars are required for the worker to start in `dev` mode. The HTTP API will boot without them but `/api/token` returns 500.
- `backend/uploads/` is gitignored — uploaded PDFs are local-only by default. Switch to S3 via `STORAGE_BACKEND=s3`. For S3, the upload route streams the object to a temp file before calling `Retriever.ingest_pdf` (see `_ingest_stored_pdf` in `app/api/routes/documents.py`).
- Document upload is **two-phase**: `POST /api/documents` stores bytes and returns `status="uploaded"`; the frontend then calls `POST /api/documents/{id}/ingest` which runs the synchronous `Retriever.ingest_pdf` and writes a `{doc_id}/meta.json` sidecar marking the doc indexed. If ingestion raises, the route returns 502 but **preserves** the stored PDF so the Library page's "Re-index" button can retry without re-upload.
- TTS defaults are Cartesia-shaped (`TTS_VOICE` is a UUID). Replace `TTS_MODEL` and `TTS_VOICE` when switching `TTS_PROVIDER` (`cartesia | elevenlabs | openai`). ElevenLabs also reads `TTS_LANGUAGE` and `ELEVEN_API_KEY`.
- `LLM_PROVIDER` Literal only allows `"openai"` today. Add to the Literal before changing `.env`.
- `BOARD_READER` defaults to `"null"` (no-op). Set `BOARD_READER=openai_vision` (needs `OPENAI_API_KEY`) to feed user-board snapshots through `gpt-4o-mini` (configurable via `BOARD_READER_MODEL`). Snapshot cadence is `BOARD_READER_INTERVAL_SECONDS` (2s) and is debounced inside `app/agent/whiteboard/listener.py`.
- `BOARD_EXTRACTOR` defaults to `"null"` (no-op). Set `BOARD_EXTRACTOR=openai` (needs `OPENAI_API_KEY`) to enable the sentence-streaming AiBoard writer (`gpt-4o-mini` by default; override with `BOARD_EXTRACTOR_MODEL`, timeout via `BOARD_EXTRACTOR_TIMEOUT_SECONDS`).
- `uv.lock` is gitignored; `uv sync` regenerates it.
- `pytest-asyncio` is in `auto` mode — async test functions don't need `@pytest.mark.asyncio`.
- **Agent persona is YAML, not env.** `Settings.agent_instructions` is a `@property` that calls `_load_persona(persona_file)` — there is no `AGENT_INSTRUCTIONS` env var anymore. The default `backend/personas/default.yaml` ships a math-tutor prompt; swap with `PERSONA_FILE=/path/to/other.yaml` (the YAML must define a non-empty top-level `instructions:` string).
- **Phoenix tracing must be imported first.** `app/agent/main.py` calls `setup_phoenix()` at the top of the module, before any `livekit` or provider imports. Don't reorder — livekit caches unpatched OpenAI/LlamaIndex method references and the spans go missing. The HTTP API (`app/api/main.py`) does the same on its hot path.
- **Observability deps are an optional extra.** `uv sync --extra observability` pulls `arize-phoenix`, `openinference-instrumentation-openai`, and `openinference-instrumentation-llama-index`. Without them, `PHOENIX_ENABLED=true` logs a warning and falls back to a no-op (does not crash).
