# File / module index

Hand-maintained map of every important file. Update this when adding or renaming files. See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the *why* and [`../CLAUDE.md`](../CLAUDE.md) for the rules.

## Root

| Path | What it is |
| --- | --- |
| `CLAUDE.md` | Agent guidance — commands, architecture rules, where to add things. |
| `AGENTS.md` | Pointer file for non-Claude agents. |
| `README.md` | Human-facing project README. |
| `docs/ARCHITECTURE.md` | "Why" / "how" companion to `CLAUDE.md`. |
| `docs/INDEX.md` | This file — hand-maintained file/module map. |
| `docs/improvement-plan/README.md` | Links to GitHub improvement-plan issues (#28–#36). |
| `.env.example` | Canonical env template. Copy to `.env` at repo root. |
| `.env` | (gitignored) — actual secrets. Read by `backend/app/config.py`. |

## `backend/` — Python (LiveKit worker + FastAPI)

| Path | What it is |
| --- | --- |
| `backend/pyproject.toml` | Deps + ruff + pytest config. Add new vendor plugins here. |
| `backend/.python-version` | Python 3.11+ pin for `uv`. |
| `backend/README.md` | Backend-specific run instructions. |
| `backend/CLAUDE.md` | Backend-scoped agent guidance (rules, gotchas, where-to-add map). |
| `backend/uploads/` | (gitignored) — default `STORAGE_LOCAL_DIR`. |
| `backend/tests/` | Pytest suite — `tests/rag/`, `tests/whiteboard/`, `tests/simulation/`, `tests/auth/`, `tests/api/`, `tests/progress/`, `tests/agent/` (incl. `turn_context/`). |
| `backend/personas/default.yaml` | YAML system prompt loaded by `Settings.agent_instructions`. Swap via `PERSONA_FILE`. |
| `backend/evals/README.md` | Agent-facing guide to the retrieval evaluation pipeline, reports, chunking policies, dashboard wiring, and extension workflow. |
| `backend/evals/golden/goodfellow_ch2_retrieval.jsonl` | 40-row golden retrieval set for Goodfellow chapter 2. |
| `backend/evals/golden/goodfellow_ch2_structured.jsonl` | 40-row golden set for structured lookup (page/section/figure/equation/example/chapter/mixed). |
| `backend/scripts/eval_retrieval.py` | CLI to compare retrieval quality across embedding collections. |
| `backend/scripts/eval_chunking.py` | CLI to parse once, index multiple chunking policies, evaluate them, and optionally update the frontend dashboard JSON. |
| `backend/scripts/eval_structured.py` | CLI to compare production, structured-only, and semantic-only retrieval paths; optional dashboard JSON output. |
| `backend/scripts/simulate_conversation.py` | CLI to replay YAML tutor scenarios against the real agent stack (text-only, no voice). |
| `backend/simulations/scenarios/` | YAML conversation scenarios for `simulate_conversation.py`. |

### `backend/app/` — shared package

| Path | What it is |
| --- | --- |
| `app/config.py` | `Settings` (pydantic-settings) + provider `Literal` types + `get_settings()`. **All env-driven config lives here.** |
| `app/observability.py` | Arize Phoenix tracing. Idempotent `setup_phoenix()` instruments OpenAI + LlamaIndex when `PHOENIX_ENABLED=true`. Imported at the top of `app/agent/main.py` and `app/api/main.py`. |

### `backend/app/agent/` — LiveKit worker

| Path | What it is |
| --- | --- |
| `agent/main.py` | Worker `entrypoint(ctx)` — joins a room, builds `AgentSession`, starts greeting. CLI: `python -m app.agent.main dev`. |
| `scripts/agent_console.py` | Interactive text REPL with readable tutor output (`backend/scripts/`, not under `app/agent/`). |
| `agent/session_factory.py` | Production per-room wiring: `build_session_bundle`, `resolve_session_identity`, `send_initial_greeting`. |
| `agent/turn_context/` | Turn pipeline: `prepare.py` (injection + grader scheduling), `builder.py`, `grade.py`, `grading_task.py`, `snapshot.py`, `session.py`, `types.py`. |
| `agent/console/` | Local text console — `runtime.py`, `identity.py`, `ui.py`, `render.py`, `turn.py`, `loop.py`. |
| `agent/simulation/scenarios.py` | YAML scenario loader (`ConversationScenario`, `load_scenario`). Turn expectations include per-turn progression fields (`node_level`, `focus_node`, `next_suggestion_node`, `misconceptions_contain`). |
| `agent/simulation/assertions.py` | Turn expectations checked against LiveKit `RunResult` events + optional `ProgressEngine` state. |
| `agent/tools.py` | `@function_tool` functions the LLM can call. `build_function_tools()` assembles the LLM-facing list (see tool table below). `update_ai_board` / `clear_ai_board` stay defined for tests but are not exposed to the LLM. |
| `agent/providers/__init__.py` | Re-exports `build_stt/llm/tts/vad`. |
| `agent/providers/register.py` | Eager LiveKit plugin imports on the main thread (required before local scripts). |
| `agent/providers/stt.py` | STT factory. Branches on `settings.stt_provider`. Lazy vendor imports. |
| `agent/providers/llm.py` | LLM factory. |
| `agent/providers/tts.py` | TTS factory. Cartesia / ElevenLabs / OpenAI. |
| `agent/providers/vad.py` | VAD factory. Silero only today. |
| `agent/whiteboard_agent.py` | `Agent` subclass: `on_user_turn_completed` → `prepare_turn_context`; tees transcription to the AiBoard extractor. Grader runs in background via `turn_context/`, not inline here. |

#### LLM function tools (`agent/tools.py`)

Progress is **grader-primary**: the tutor LLM never mutates progress — the grader (`app/agent/grader/`) applies `GradeResult` via `ProgressEngine.apply_grade_result()` after each student turn. Tutor tools are read-only for progress.

| Tool | In LLM list when | Role |
| --- | --- | --- |
| `search_documents` | always | RAG lookup via `get_retriever()` |
| `read_user_board` | always | Latest student-board OCR text |
| `get_progress` | syllabus + progress loaded | Read-only progress summary (same text as injected `[session progress]` block) |
| `list_problems` | syllabus + progress loaded | Read-only syllabus problem listing, optional chapter/concept filter |
| `update_ai_board` | never (defined only) | Publish primitive for tests; AiBoard is extractor-driven |
| `clear_ai_board` | never (defined only) | Same — not in `build_function_tools()` |

Superseded tutor mutating tools (removed from `build_function_tools()`): `set_focus`, `record_mastery`. Grader-primary architecture: progress mutations flow through `app/agent/grader/` + `ProgressEngine.apply_grade_result()`, not tutor tools.

### `backend/app/agent/whiteboard/extractor/` — sentence-streaming AiBoard writer

| Path | What it is |
| --- | --- |
| `extractor/base.py` | `BoardExtractor` Protocol + sentence input types. |
| `extractor/null.py` | `NullBoardExtractor` — no-op default. |
| `extractor/openai.py` | `OpenAIBoardExtractor` — structured-outputs board items per sentence. |
| `extractor/factory.py` | `get_board_extractor()` — env-driven factory (`BOARD_EXTRACTOR`). |

### `backend/app/agent/whiteboard/` — pluggable handwriting reader + state

| Path | What it is |
| --- | --- |
| `whiteboard/__init__.py` | Re-exports `BoardState`, `get_board_reader`, `publish_ai_board`, `install_user_board_listener`, and the wire-format schemas. |
| `whiteboard/messages.py` | pydantic schemas for `ai_board` (server→clients) and `user_board` (clients→server) data-channel topics. |
| `whiteboard/state.py` | `BoardState` — per-room cache of the latest user-board reading. |
| `whiteboard/publisher.py` | `publish_ai_board(room, update)` — encodes + sends an `AiBoardUpdate`. |
| `whiteboard/listener.py` | `install_user_board_listener(...)` — debounced data-received pipeline that feeds the `BoardReader`. |
| `whiteboard/reader/__init__.py` | `BoardReader` Protocol + `get_board_reader()` factory. |
| `whiteboard/reader/null.py` | `NullBoardReader` — no-op default. |
| `whiteboard/reader/openai_vision.py` | `OpenAIVisionBoardReader` — vision-LLM handwriting recognition. |
| `whiteboard/sentence.py` | Sentence splitter for extractor pipeline. |
| `whiteboard/cache.py` | Per-room AiBoard item cache. |

### `backend/app/auth/` — Google OAuth + session JWT

| Path | What it is |
| --- | --- |
| `auth/jwt.py` | Issue/decode session JWT (`AUTH_JWT_SECRET`). |
| `auth/google.py` | Google OAuth client helpers. |
| `auth/store.py` | `UserStore` — SQLite user persistence. |
| `auth/deps.py` | `get_current_user`, `get_optional_user` FastAPI dependencies. |

### `backend/app/documents/` — shared catalog helpers

| Path | What it is |
| --- | --- |
| `documents/catalog.py` | `list_document_summaries`, sidecar key helpers — shared by HTTP API and console doc picker. |

### `backend/app/agent/grader/` — per-turn student-model grader

A second LLM seam (mirrors `whiteboard/extractor/`) that assesses each student
turn and advances mastery levels / misconceptions via `ProgressEngine.apply_grade_result()`,
so the student model evolves every turn without the tutor LLM calling mutating
progress tools. Off in code by default (`GRADER=null` in `Settings`); opt in with
`GRADER=openai` (see `.env.example`).

| Path | What it is |
| --- | --- |
| `grader/base.py` | `Grader` Protocol, `GradeResult`, `NodeUpdate` (the graded payload). |
| `grader/null.py` | `NullGrader` — no-op default; progress state loads but does not advance. |
| `grader/openai.py` | `OpenAIGrader` — structured-outputs grader over the turn + board + focus context. |
| `grader/fake.py` | `FakeGrader` — scripted queue of `GradeResult`s for YAML simulators (`simulate_conversation.py`). |
| `grader/factory.py` | `get_grader()` — env-driven `@lru_cache`d factory (`GRADER`, `GRADER_MODEL`, `GRADER_TIMEOUT_SECONDS`). |

### `backend/app/progress/` — knowledge-tracing student model

Tracks per-`(user_id, doc_id)` progress over the syllabus tree. Both concepts
and problems are trackable units (a concept with no problems still progresses).
Mastery is ordinal (`not_started < introduced < practicing < proficient < mastered`)
so partial progress is observable. A v1 → v2 migration runs transparently on load.

| Path | What it is |
| --- | --- |
| `progress/models.py` | `ProgressState`, `NodeProgress`, `FocusPointer`, `ProgressSummary`, `MasteryLevel`, `Recommendation`. v1→v2 migration validator. |
| `progress/engine.py` | `ProgressEngine` — state machine: `set_focus`, `set_level` (monotonic), `record_mastery`, `apply_grade_result` (grader write path), `record_misconception`/`clear_misconceptions`, `record_hint`, `effective_level` (concept aggregation), `recommend()` (deterministic directive), `format_injection()` / `snapshot_update()` (wire). |
| `progress/messages.py` | Wire schemas for the `session_progress` topic: `SessionProgressUpdate`, `ProblemProgressSnapshot` (5-level `status`), `ConceptProgressSnapshot`. |
| `progress/publisher.py` | `publish_session_progress(room, update)` — encodes + sends on the data channel. |
| `progress/store.py` | `StorageProgressStore` — persists `ProgressState` JSON in storage. |

### `backend/app/syllabus/` — textbook structure tree

| Path | What it is |
| --- | --- |
| `syllabus/models.py` | `Syllabus`, `Chapter`, `Concept`, `Problem` pydantic models. |
| `syllabus/builder.py` | `build_heuristic_syllabus(document)` — maps parsed blocks → chapters/concepts/problems. |
| `syllabus/store.py` | `save_syllabus` / `load_syllabus` — storage key `{doc_id}/syllabus.json`. |
| `syllabus/parse.py` | `parse_pdf_to_document` — LlamaParse → `ParsedDocument` (gated on `LLAMAPARSE_API_KEY`). |

### `backend/app/api/` — FastAPI HTTP API

| Path | What it is |
| --- | --- |
| `api/main.py` | FastAPI app, CORS, mounts routers, `/health`. |
| `api/routes/token.py` | `POST /api/token` — signs LiveKit JWT, returns `{token, url, room, identity}`. |
| `api/routes/auth.py` | `GET /api/auth/google`, callback, `GET /api/auth/me`, `POST /api/auth/logout`. |
| `api/routes/documents.py` | `POST /api/documents`, `POST /api/documents/{doc_id}/ingest`, `GET /api/documents`, `GET /api/documents/{doc_id}/file`, `GET /api/documents/{doc_id}/syllabus`. |
| `api/routes/progress.py` | `GET/PATCH /api/progress/{doc_id}` — per-user progress REST (debug/UI). |

### `backend/app/storage/` — pluggable storage

| Path | What it is |
| --- | --- |
| `storage/base.py` | `StorageBackend` Protocol, `StoredObject` dataclass, `get_storage()` factory. |
| `storage/local.py` | `LocalStorage` — filesystem with path-traversal defense. |
| `storage/s3.py` | `S3Storage` — boto3 wrapper. Activated via `STORAGE_BACKEND=s3`. |

### `backend/app/rag/` — pluggable retrieval

| Path | What it is |
| --- | --- |
| `rag/retriever.py` | `Retriever` Protocol, `RetrievedChunk`, `NullRetriever`, and `get_retriever()` provider factory. |
| `rag/parsing.py` | Normalized textbook parse models, retrieval request/result models, and parser protocol. |
| `rag/llamaparse_parser.py` | Llama Cloud/LlamaParse adapter that parses PDF textbooks into normalized documents. |
| `rag/normalizer.py` | Converts LlamaParse structured items into page-aware textbook blocks. |
| `rag/indexing.py` | Converts normalized blocks into LlamaIndex nodes with Qdrant metadata; includes built-in chunking policy registry for evals. |
| `rag/query_parser.py` | Detects page/problem/example references in student queries. |
| `rag/formatter.py` | Converts internal retrieved records into cited `RetrievedChunk` results. |
| `rag/llamaindex_qdrant.py` | Concrete LlamaIndex + Qdrant retriever implementation. |
| `rag/multi_ingest.py` | Multi-collection ingest helpers for evals. |
| `rag/embeddings.py` | Embedding model registry for eval comparisons. |
| `rag/reference_ids.py` | Stable reference id helpers for chunks. |
| `rag/evaluation.py` | Golden-set retrieval evaluation: loads JSONL cases, scores retrieved chunks, aggregates metrics, and renders reports. |
| `rag/__init__.py` | Re-exports the public RAG seam. |

## `frontend/` — Vite + React + TypeScript

| Path | What it is |
| --- | --- |
| `frontend/package.json` | `dev` / `build` / `lint` (tsc-only) / `test` / `preview` scripts. |
| `frontend/vite.config.ts` | Vite config (React plugin). |
| `frontend/tsconfig*.json` | TypeScript project refs. |
| `frontend/.env.local` | (gitignored) — `VITE_API_BASE_URL`, `VITE_GUEST_ENABLED`, optional `VITE_EVALS_ENABLED`. |
| `frontend/.env.example` | Template for above. LiveKit URL comes from `POST /api/token`, not a frontend env var. |
| `frontend/src/data/embeddingEval.generated.json` | Generated embedding comparison report consumed by the eval dashboard. Update via `scripts.eval_retrieval --frontend-output`. |
| `frontend/src/data/chunkingEval.generated.json` | Generated chunking comparison report consumed by the eval dashboard. Update via `scripts.eval_chunking --frontend-output`. |
| `frontend/src/data/structuredEval.generated.json` | Generated structured lookup comparison report consumed by the eval dashboard. Update via `scripts.eval_structured --frontend-output`. |

### `frontend/src/`

| Path | What it is |
| --- | --- |
| `src/main.tsx` | React entry — mounts `<App />` into the root. |
| `src/App.tsx` | `react-router-dom` shell — `/login`, `/` (auth), `/session` (auth or `?guest=true`), `/evals`. |
| `src/vite-env.d.ts` | Vite/TS environment types. |
| `src/lib/api.ts` | Primary REST client: documents, token, syllabus. |
| `src/lib/auth.ts` | Session helpers: `getMe`, `logout` (consolidate into `api.ts` in Phase 4). |
| `src/lib/progress.ts` | TS mirror of `progress/messages.py` + decode helpers. |
| `src/lib/roadmapProgress.ts` | Roadmap panel view-model types (`ProblemStatus` mirror). |
| `src/lib/syllabus.ts` | Syllabus tree types from `GET /api/documents/{id}/syllabus`. |
| `src/lib/activeDoc.ts` | `localStorage` key for library → session active doc. |
| `src/data/retrievalEval.ts` | Normalizes generated backend eval JSON into dashboard-friendly TypeScript types. |
| `src/lib/useTypewriter.ts` | Hook used by the transcript bubbles. |
| `src/pages/LoginPage.tsx` | Google OAuth entry + guest link when `VITE_GUEST_ENABLED`. |
| `src/pages/UploadPage.tsx` | Landing page — `<PdfDropZone>` + uploaded-doc list (upload then ingest). |
| `src/pages/SessionPage.tsx` | Wraps `<LiveKitRoom>` + `SharedReasoningWorkspace` + voice footer. |
| `src/pages/EvalDashboardPage.tsx` | Internal RAG/chunking eval comparison dashboard (`/evals`). |
| `src/components/auth/AuthGate.tsx` | Redirects unauthenticated users to `/login`. |
| `src/components/progress/RoadmapProgressPanel.tsx` | Syllabus roadmap UI driven by `session_progress` channel. |
| `src/components/progress/SessionProgressBridge.tsx` | Subscribes to progress channel, provides snapshot context. |
| `src/components/progress/useProgressChannel.ts` | Typed `useDataChannel("session_progress")` wrapper. |
| `src/components/library/DocList.tsx` | Library document list with ingest status. |
| `src/components/PdfDropZone.tsx` | File-picker / drag-drop component for PDFs. |
| `src/components/Transcript.tsx` | Streamed user + agent transcription, typewriter animation. |
| `src/components/session/SessionTopbar.tsx` | Shared top bar; renders the End-session control in session mode. |
| `src/components/session/VoiceComposer.tsx` | Mic toggle + visualizer; wraps `useTrackToggle` / `useVoiceAssistant`. |
| `src/styles/global.css` | App-wide base styles. |
| `src/styles/session.css` | Session-page layout, voice composer, and both whiteboards. |
| `src/lib/whiteboard.ts` | TS mirror of `backend/app/agent/whiteboard/messages.py` + encode/decode helpers. |
| `src/components/session/SharedReasoningWorkspace.tsx` | Session canvas shell; subscribes to `ai_board`, hosts tutor objects + handwriting panel. |
| `src/components/session/TutorObjectLayer.tsx` | Draggable tutor object cards rendered from workspace state. |
| `src/components/session/HandwritingPanel.tsx` | Student handwriting canvas; publishes `user_board` snapshots. |
| `src/components/whiteboard/BoardItem.tsx` | Switch on `item.kind` → KaTeX / inline SVG plot / sanitized SVG. |
| `src/components/whiteboard/useBoardChannel.ts` | Typed `useDataChannel` wrapper for one board topic. |
