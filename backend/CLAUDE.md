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
2. **Provider/storage/retriever choices are `Literal` types.** Adding a new option = add to the Literal + add a branch in the factory + add the dep. Never modify call sites.
3. **Vendor SDKs stay isolated to provider boundaries.** `from livekit.plugins import deepgram` lives in `app/agent/providers/stt.py` and not in business code. Same rule for `openai`, `cartesia`, `boto3`, LlamaIndex, Qdrant, etc.: keep vendor imports inside agent provider modules, storage modules, and RAG implementation modules or factory branches under `app/rag/`. Lazy imports keep startup fast and let users skip plugins they don't need.
4. **Function tools are the agent's API surface.** New LLM-callable capabilities = a new `@function_tool` async function in `app/agent/tools.py`, returned from `build_function_tools()`. The agent picks it up automatically. **Write the docstring carefully** — the LLM reads it.
5. **`Settings` reads `.env` AND `../.env`.** The repo-root `.env` is the canonical location for shared secrets. `backend/README.md` says `cp ../.env.example ../.env`.
6. **Singletons are cached.** `get_settings()`, `get_storage()`, `get_retriever()` are all `lru_cache` or module-level. Restart the process to pick up env changes; clear caches in tests.

## Quick "where to add..." map

| Task | File(s) |
| --- | --- |
| New STT/LLM/TTS/VAD vendor | `app/agent/providers/<modality>.py` + `Literal` in `config.py` + dep in `pyproject.toml` |
| New LLM capability | `app/agent/tools.py` (new `@function_tool`, add to `build_function_tools`) |
| Built-in RAG implementation | Set `RAG_PROVIDER=llamaindex_qdrant`; add a new module under `app/rag/` only for another provider. |
| New HTTP endpoint | New file in `app/api/routes/`, mount in `app/api/main.py` |
| New storage backend | New file in `app/storage/` implementing `StorageBackend`; branch in `get_storage()` + `Literal` |
| New env var | Field on `Settings` in `app/config.py` + entry in `../.env.example` |
| Tune agent persona | `Settings.agent_instructions` default, or `AGENT_INSTRUCTIONS` env var |

## Gotchas

- `LIVEKIT_*` env vars are required for the worker to start in `dev` mode. The HTTP API will boot without them but `/api/token` returns 500.
- `backend/uploads/` is gitignored — uploaded PDFs are local-only by default. Switch to S3 via `STORAGE_BACKEND=s3`.
- TTS defaults are Cartesia-shaped (`TTS_VOICE` is a UUID). Replace `TTS_MODEL` and `TTS_VOICE` when switching `TTS_PROVIDER`.
- `LLM_PROVIDER` Literal only allows `"openai"` today. Add to the Literal before changing `.env`.
- `uv.lock` is gitignored; `uv sync` regenerates it.
- `pytest-asyncio` is in `auto` mode — async test functions don't need `@pytest.mark.asyncio`.
