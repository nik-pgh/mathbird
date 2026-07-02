# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

LiveKit voice agent with a configurable STT/LLM/TTS/VAD pipeline plus a React frontend for uploading PDFs the agent can reason over. Deployed to **LiveKit Cloud** — no self-hosted SFU. The voice session is accompanied by twin in-room whiteboards on a LiveKit data channel: an `AiBoard` the agent writes to (typeset math, plots, SVG shapes) and a `UserBoard` the student draws on (snapshots get OCR'd into the agent's chat context). RAG is a configurable seam: the default `RAG_PROVIDER=null` uses `NullRetriever` so local no-RAG operation still runs end-to-end, and `RAG_PROVIDER=llamaindex_qdrant` enables the built-in LlamaParse + LlamaIndex + Qdrant implementation. A finer-grained file/module index lives in [`docs/INDEX.md`](./docs/INDEX.md); deeper architectural rationale is in [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md).

## Repo layout (two apps in one repo)

```
mathbird/
├── .env                       # root env, read by backend (Settings looks at .env AND ../.env)
├── backend/                   # Python 3.11+, two processes share one package
│   ├── app/
│   │   ├── config.py          # pydantic-settings Settings — single env source of truth
│   │   ├── auth/              # Google OAuth, JWT session cookies, SQLite user store
│   │   ├── agent/             # LiveKit worker
│   │   │   ├── main.py        # entrypoint — joined per room
│   │   │   ├── session_factory.py  # per-room wiring (progress, syllabus, tools)
│   │   │   ├── tools.py       # @function_tool functions (RAG + read-only progress)
│   │   │   ├── whiteboard_agent.py  # Agent subclass; turn prep + AiBoard extractor
│   │   │   ├── turn_context/  # prepare_turn_context, parallel grader scheduling
│   │   │   ├── grader/        # per-turn student-model grader (GRADER env)
│   │   │   ├── providers/     # stt.py / llm.py / tts.py / vad.py — factories
│   │   │   └── whiteboard/    # messages, listener, reader/, extractor/
│   │   ├── progress/          # ProgressEngine, persistence, session_progress wire
│   │   ├── syllabus/          # syllabus tree built at ingest from ParsedDocument
│   │   ├── documents/         # catalog.py — shared PDF listing helpers
│   │   ├── api/               # FastAPI (token, uploads, auth, progress)
│   │   │   └── routes/        # token.py, documents.py, auth.py, progress.py
│   │   ├── storage/           # base.py (Protocol) + local.py / s3.py
│   │   ├── observability.py   # Arize Phoenix tracing (PHOENIX_ENABLED)
│   │   └── rag/               # Retriever Protocol + LlamaIndex/Qdrant pipeline
│   ├── scripts/               # agent_console, eval_*, simulate_conversation
│   └── personas/              # YAML system prompts; PERSONA_FILE picks which one
└── frontend/                  # Vite + React + TS
    └── src/
        ├── App.tsx            # react-router: /, /login, /session, /evals
        ├── lib/
        │   ├── api.ts         # typed REST client (sole fetch site)
        │   ├── whiteboard.ts  # TS mirror of whiteboard pydantic schemas
        │   ├── progress.ts    # TS mirror of session_progress wire format
        │   └── roadmapProgress.ts  # roadmap UI types (ProblemStatus mirror)
        ├── pages/             # UploadPage, SessionPage, LoginPage, EvalDashboardPage
        ├── components/
        │   ├── auth/          # AuthGate
        │   ├── progress/      # RoadmapProgressPanel, useProgressChannel
        │   ├── session/       # SharedReasoningWorkspace, HandwritingPanel, …
        │   └── whiteboard/    # BoardItem.tsx, useBoardChannel.ts
        └── styles/            # global.css, session.css
```

## Commands

All backend commands run from `backend/` and use `uv` (preferred) — fall back to `pip install -e ".[dev]"` if `uv` is unavailable.

```bash
# Backend — install
cd backend && uv sync

# Backend — HTTP API (PDF upload + LiveKit token), reload on change
uv run uvicorn app.api.main:app --reload --port 8000

# Backend — LiveKit agent worker (connects to LiveKit Cloud, joins rooms)
uv run python -m app.agent.main dev

# Backend — agent text console (no mic; debug LLM + tools locally)
uv run python -m scripts.agent_console

# Backend — scripted conversation simulation from YAML
uv run python -m scripts.simulate_conversation simulations/scenarios/tutor_greeting.yaml -v

# Backend — lint / format
uv run ruff check .
uv run ruff format .

# Backend — tests (pytest-asyncio is in auto mode)
uv run pytest
uv run pytest path/to/test_file.py::test_name   # single test

# Frontend — install + run dev server (Vite on :5173)
cd frontend && npm install && npm run dev

# Frontend — typecheck (the "lint" script is `tsc -b --noEmit`)
npm run lint

# Frontend — production build
npm run build
```

The agent worker **needs LiveKit Cloud credentials in `.env`** to start in `dev` mode (it registers as a worker against the cloud SFU). The HTTP API will start without them but `/api/token` returns 500. Google OAuth (`GOOGLE_CLIENT_ID`, `AUTH_JWT_SECRET`) is required for authenticated library access; set `GUEST_SAMPLE_DOC_ID` on the backend and `VITE_GUEST_ENABLED=true` on the frontend for guest voice sessions.

## Authentication

- **Library routes** (`/`, upload, document list) require a session cookie from Google OAuth (`GET /api/auth/google` → callback → HttpOnly cookie).
- **Guest mode**: `/session?guest=true` skips `AuthGate` and requests a LiveKit token without login; backend falls back to `GUEST_SAMPLE_DOC_ID` when no `doc_id` is supplied.
- **Token metadata**: authenticated sessions embed `user_id` and optional `active_doc_id` in the LiveKit participant JWT so the worker can load per-user progress and scope RAG.

## How a conversation flows (mental model for changes)

1. Frontend `POST /api/token` (with session cookie or as guest) → FastAPI signs a LiveKit JWT, returns `{token, url, room, identity}`.
2. Frontend connects to LiveKit Cloud with that JWT and joins the room. `SessionPage` mounts `SharedReasoningWorkspace` (tutor object cards + handwriting panel + roadmap progress) alongside the audio UI.
3. The agent worker is registered with LiveKit Cloud — when a participant joins, LiveKit dispatches `app.agent.main.entrypoint` into the room. The entrypoint installs a `user_board` data-channel listener, attaches per-room `SessionData` (board state, progress engine when loaded), and starts a `WhiteboardAgent`.
4. Worker streams audio → STT → LLM → TTS → audio back into the room. The LLM can call function tools:
   - `search_documents` — RAG lookup through `get_retriever()`.
   - `read_user_board` — re-read the latest cached `BoardState` snapshot mid tool-chain.
   - `get_progress` / `list_problems` — read-only syllabus progress (only when syllabus + progress are loaded for the session).
   Progress **mutations** are **not** tutor tools — they flow through the **grader** (step 5). The AiBoard is driven separately: `WhiteboardAgent.transcription_node` tees the agent's outgoing text stream, accumulates sentences, and a background worker calls the configured `BoardExtractor` (`null` or `openai`) which publishes `update_ai_board` items over the data channel per sentence. The LLM does NOT call `update_ai_board` directly.
5. After each student turn, when syllabus + progress are loaded and `GRADER` is not `null`, `prepare_turn_context` (`app/agent/turn_context/prepare.py`) schedules the grader **in the background** while the tutor composes its reply. Turn N+1 drains the in-flight grade-N task before injecting `[session progress]` and `[next action]`, so the tutor sees grade N−1 state on turn N and grade N state on turn N+1. The grader returns a `GradeResult` that `ProgressEngine.apply_grade_result()` applies, persists, and publishes on `session_progress` when the background task completes.
6. In parallel, the handwriting panel periodically posts PNG snapshots on the `user_board` topic. The listener decodes, debounces, hands the bytes to the configured `BoardReader` (`null` or `openai_vision`), and writes the resulting text into `BoardState`.

You do **not** run a LiveKit server locally. The worker is a client that joins cloud rooms on demand.

## Architectural rules (these are load-bearing — don't break them)

These come from the README's "Project conventions" and the actual code shape. Violating them defeats the whole swappable-vendor design:

1. **No vendor SDKs in business code.** The agent never imports `deepgram` / `openai` / `cartesia` / `elevenlabs` / `qdrant` / etc. directly. Vendor imports live only in `backend/app/agent/providers/*.py` (STT/LLM/TTS/VAD), `backend/app/storage/*.py` (local/s3), RAG provider modules under `backend/app/rag/`, and board-reader implementations under `backend/app/agent/whiteboard/reader/`. Anything else uses the LiveKit base types or our own Protocols.
2. **One env var per knob, all defined on `Settings`.** Don't read `os.environ` outside `app/config.py`. Add the field to `Settings`, then read it via `get_settings()`.
3. **Adding a provider = add a branch + extend the `Literal` type.** Never edit call sites. To add a new TTS vendor, for example:
   - Add the dep (or LiveKit plugin extra) to `backend/pyproject.toml`.
   - Add an `if name == "...":` branch in `app/agent/providers/tts.py`.
   - Add the name to the `TtsProvider` Literal in `app/config.py`.
   - That's it — `app/agent/main.py` is untouched. The same shape applies to STT/LLM/VAD providers, storage backends, RAG providers, and board readers.
4. **Storage, retrieval, and board reading are Protocols, not base classes.** `StorageBackend`, `Retriever`, and `BoardReader` are `typing.Protocol` types. Implementations are duck-typed; they don't subclass anything.
5. **Function tools are the LLM's window into the codebase.** New agent capabilities are usually new `@function_tool` functions added to `backend/app/agent/tools.py` and returned from `build_function_tools()`. The agent picks them up automatically. **Docstrings are load-bearing** — the LLM reads them to decide when to call the tool. Progress is **grader-primary**: tutor tools are read-only (`get_progress`, `list_problems`); do not re-expose mutating progress tools to the LLM — extend `app/agent/grader/` instead.
6. **Whiteboard messages are typed end-to-end.** Wire schemas live in `backend/app/agent/whiteboard/messages.py` (pydantic) and are mirrored by hand in `frontend/src/lib/whiteboard.ts`. There is no codegen, so update both sides in the same change.

## Where to add things

| You want to… | Touch this |
| --- | --- |
| Swap STT/LLM/TTS/VAD vendor | `.env` only (selections are validated against the `Literal` types in `config.py`) |
| Add a new vendor for an existing modality | `app/agent/providers/<modality>.py` + `Literal` in `config.py` + dep in `pyproject.toml` |
| Plug in real RAG | Set `RAG_PROVIDER=llamaindex_qdrant` for the built-in LlamaParse + Qdrant retriever; add a new module under `app/rag/` only for another provider. |
| Add a new agent capability (callable mid-conversation) | New `@function_tool` in `app/agent/tools.py`, add to `build_function_tools()` |
| Change how progress advances | `app/agent/grader/<name>.py` + `GraderName` in `config.py` + branch in `grader/factory.py` — not tutor tools |
| Add a new whiteboard item kind | Add a pydantic model to `app/agent/whiteboard/messages.py`, extend the `AiBoardItem` union, mirror in `frontend/src/lib/whiteboard.ts`, render in `frontend/src/components/whiteboard/BoardItem.tsx` |
| Add a new board reader (handwriting recognizer) | New module under `app/agent/whiteboard/reader/`, add the name to `BoardReaderName` in `config.py`, add a branch in `get_board_reader()` |
| Add a new board extractor (sentence-streaming AiBoard writer) | New module under `app/agent/whiteboard/extractor/`, add the name to `BoardExtractorName` in `config.py`, add a branch in `get_board_extractor()` |
| Change agent persona / system prompt | Edit `backend/personas/default.yaml`, or point `PERSONA_FILE` at a different YAML file (loaded by `Settings.agent_instructions`) |
| Add a new HTTP endpoint | New router in `app/api/routes/`, mount in `app/api/main.py` |
| Add Google OAuth / session auth knob | Field on `Settings` in `app/config.py` + `app/auth/` + `app/api/routes/auth.py` |
| Change parallel grader timing | `app/agent/turn_context/prepare.py`, `grading_task.py`, `grade.py` |
| Switch PDF storage to S3 | `STORAGE_BACKEND=s3` + `S3_*` / `AWS_*` env vars — no code changes |
| Change the API base URL the frontend hits | `VITE_API_BASE_URL` in `frontend/.env.local` |

## Frontend ↔ backend contract

There are three contracts the frontend and backend must keep in sync — all hand-mirrored, no codegen:

**1. REST.** `frontend/src/lib/api.ts` is the **only** `fetch()` site for REST — documents, LiveKit token, syllabus, and session auth (`getMe`, `logout`).

| Call | Backend route | Returns |
| --- | --- | --- |
| `getMe()` | `GET /api/auth/me` | `User \| null` |
| `logout()` | `POST /api/auth/logout` | — |
| `uploadPdf(file)` | `POST /api/documents` | `UploadedDocument` (`status="uploaded"`) |
| `ingestDocument(docId)` | `POST /api/documents/{doc_id}/ingest` | `UploadedDocument` (`status="indexed"`) |
| `listDocuments()` | `GET /api/documents` | `UploadedDocument[]` |
| `documentFileUrl` / `fetchDocumentPdfBlob` | `GET /api/documents/{doc_id}/file` | PDF bytes |
| `fetchDocumentSyllabus(docId)` | `GET /api/documents/{doc_id}/syllabus` | `Syllabus` |
| `requestToken({doc_id?, ...})` | `POST /api/token` | `TokenResponse` (includes LiveKit `url`) |

Update `lib/api.ts` and the corresponding pydantic models in `app/api/routes/` in the same change.

**2. LiveKit data channels — whiteboard.** Two topics for board traffic:

| Topic | Direction | Payload |
| --- | --- | --- |
| `ai_board` | server → clients | `AiBoardUpdate` — `op: "upsert" \| "clear"` with `AiBoardText \| AiBoardPlot \| AiBoardShape` items |
| `user_board` | clients → server | `UserBoardSnapshot` — base64 PNG (≤512px long edge) + `captured_at_ms` + `is_empty` |

Schemas: `backend/app/agent/whiteboard/messages.py` ↔ `frontend/src/lib/whiteboard.ts`.

**3. LiveKit data channel — progress.** Third topic for the roadmap panel:

| Topic | Direction | Payload |
| --- | --- | --- |
| `session_progress` | server → clients | `SessionProgressUpdate` — full snapshot or patch of problem/concept mastery |

Schemas: `backend/app/progress/messages.py` ↔ `frontend/src/lib/progress.ts` and `frontend/src/lib/roadmapProgress.ts` (update all three together).

## Tests

Pytest config lives in `backend/pyproject.toml` with `asyncio_mode = "auto"` — async test functions don't need `@pytest.mark.asyncio`. `httpx` is in dev deps for FastAPI testing. Tests live under `backend/tests/` grouped by seam (`tests/rag/`, `tests/whiteboard/`, `tests/simulation/`, `tests/auth/`, `tests/api/`, `tests/progress/`, `tests/agent/`); add new tests next to the package they exercise. Use `@pytest.mark.live` for tests that call external LLM APIs.

The frontend has a **small Node test suite** (no Jest/Vitest): `npm test` runs pure-function scripts under `frontend/scripts/` (`test-math`, `test-canvas`, `test-board`, `test-pdf-layout`). There is no component/E2E test harness yet.

## Gotchas

- **`Settings` reads `.env` and `../.env`.** Run the backend from `backend/` and keep secrets in the repo-root `.env` — the `.env.example` at the root is the canonical template, and `backend/README.md` says `cp ../.env.example ../.env`.
- **`get_settings()`, `get_storage()`, and `get_retriever()` are `lru_cache`d / module-level singletons.** Changing env vars at runtime won't take effect; restart the process. In tests, clear the caches.
- **`uv.lock` is gitignored.** Don't be surprised if it's missing on a fresh clone; `uv sync` regenerates it.
- **`backend/uploads/` is gitignored** and is the default local storage dir (`STORAGE_LOCAL_DIR=./uploads`). Don't commit uploaded PDFs.
- **Frontend "lint" is typecheck-only** (`tsc -b --noEmit`). There's no ESLint config in the repo.
- **TTS defaults are Cartesia-shaped.** `TTS_VOICE` is a Cartesia voice UUID. If you switch `TTS_PROVIDER` (allowed values today: `cartesia | elevenlabs | openai`), also replace `TTS_MODEL` and `TTS_VOICE` — the comment block in `.env.example` lists per-provider formats. ElevenLabs additionally uses `TTS_LANGUAGE` and `ELEVEN_API_KEY`.
- **LLM provider Literal only has `"openai"` today.** The pipeline supports more, but adding one means following rule 3 above before changing `.env`.
- **`BOARD_READER` defaults to `null`.** The agent will see "no reading yet" until you set `BOARD_READER=openai_vision` (and have `OPENAI_API_KEY` set). Snapshots are throttled to `BOARD_READER_INTERVAL_SECONDS` (2s) and resized to `BOARD_READER_MAX_IMAGE_DIM` (512px) on the client.
- **Agent persona lives in a YAML file, not an env var.** `Settings.agent_instructions` is a read-only `@property` that loads `backend/personas/default.yaml` (a math-tutor prompt by default). Edit that file or point `PERSONA_FILE` at another YAML with a top-level `instructions:` string. The old `AGENT_INSTRUCTIONS` env var is gone.
- **Phoenix tracing is opt-in via env.** `app/observability.py` is a no-op unless `PHOENIX_ENABLED=true` (Phoenix/OpenInference deps are always installed with `uv sync`). When enabled it instruments OpenAI + LlamaIndex so every LLM completion, function-tool call, and `Retriever.retrieve()` is captured. `setup_phoenix()` is called at the very top of `app/agent/main.py` — before any livekit imports — so don't move that import; livekit caches unpatched method refs otherwise.
- **Progress is grader-primary with parallel timing.** When syllabus + progress load for a session, the tutor gets read-only tools (`get_progress`, `list_problems`) and per-turn `[session progress]` / `[next action]` injection reflecting **grade N−1 on turn N**. The grader runs in the background via `prepare_turn_context`; turn N+1 drains grade N before injecting. Set `GRADER=openai` (needs `OPENAI_API_KEY`) for progress to advance; code default is `GRADER=null` (`.env.example` recommends `openai` for dev). `session_factory` logs a warning when progress is loaded but grader is null.
- **PDF upload is two-phase.** `POST /api/documents` stores bytes (`status="uploaded"`); `POST /api/documents/{id}/ingest` runs parse + index synchronously today and writes `{doc_id}/meta.json`. Frontend calls both from the library page.
