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
| `backend/tests/` | Pytest suite, grouped by seam (`tests/rag/`, `tests/whiteboard/`, `tests/simulation/`). |
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
| `scripts/agent_console.py` | Interactive text REPL with readable tutor output. |
| `agent/session_factory.py` | Production per-room wiring: `build_session_bundle`, `resolve_session_identity`, `send_initial_greeting`. |
| `agent/console/` | Local text console + YAML sim helpers — `runtime.py` (local fake job + HTTP context), `identity.py` (stdin doc/user picker), `ui.py` (Rich formatters). |
| `agent/simulation/scenarios.py` | YAML scenario loader (`ConversationScenario`, `load_scenario`). Turn expectations include per-turn progression fields (`node_level`, `focus_node`, `next_suggestion_node`, `misconceptions_contain`). |
| `agent/simulation/assertions.py` | Turn expectations checked against LiveKit `RunResult` events + optional `ProgressEngine` state. |
| `agent/tools.py` | `@function_tool` functions the LLM can call. `search_documents` is the RAG seam. `build_function_tools()` returns the list. |
| `agent/providers/__init__.py` | Re-exports `build_stt/llm/tts/vad`. |
| `agent/providers/register.py` | Eager LiveKit plugin imports on the main thread (required before local scripts). |
| `agent/providers/stt.py` | STT factory. Branches on `settings.stt_provider`. Lazy vendor imports. |
| `agent/providers/llm.py` | LLM factory. |
| `agent/providers/tts.py` | TTS factory. Cartesia / ElevenLabs / OpenAI. |
| `agent/providers/vad.py` | VAD factory. Silero only today. |
| `agent/whiteboard_agent.py` | `Agent` subclass that injects the latest user-board reading into the chat context each turn. |

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

### `backend/app/agent/grader/` — per-turn student-model grader

A second LLM seam (mirrors `whiteboard/extractor/`) that assesses each student
turn and advances mastery levels / misconceptions, so the student model evolves
every turn without relying on the main LLM calling progress tools. Off by
default (`GRADER=null`); opt in with `GRADER=openai`.

| Path | What it is |
| --- | --- |
| `grader/base.py` | `Grader` Protocol, `GradeResult`, `NodeUpdate` (the graded payload). |
| `grader/null.py` | `NullGrader` — no-op default; evolution gated on LLM tool calls only. |
| `grader/openai.py` | `OpenAIGrader` — structured-outputs grader over the turn + board + focus context. |
| `grader/factory.py` | `get_grader()` — env-driven `@lru_cache`d factory. |

### `backend/app/progress/` — knowledge-tracing student model

Tracks per-`(user_id, doc_id)` progress over the syllabus tree. Both concepts
and problems are trackable units (a concept with no problems still progresses).
Mastery is ordinal (`not_started < introduced < practicing < proficient < mastered`)
so partial progress is observable. A v1 → v2 migration runs transparently on load.

| Path | What it is |
| --- | --- |
| `progress/models.py` | `ProgressState`, `NodeProgress`, `FocusPointer`, `ProgressSummary`, `MasteryLevel`, `Recommendation`. v1→v2 migration validator. |
| `progress/engine.py` | `ProgressEngine` — state machine: `set_focus`, `set_level` (monotonic), `record_mastery`, `record_misconception`/`clear_misconceptions`, `record_hint`, `effective_level` (concept aggregation), `recommend()` (deterministic directive), `snapshot_update()` (wire). |
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
| `api/routes/documents.py` | `POST /api/documents` stores PDFs, `POST /api/documents/{doc_id}/ingest` indexes them, `GET /api/documents` lists upload/index status, and `GET /api/documents/{doc_id}/file` streams PDFs to the session iframe. |
| `documents/catalog.py` | Shared PDF listing for HTTP API and console doc picker (`list_document_summaries`). |

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
| `rag/evaluation.py` | Golden-set retrieval evaluation: loads JSONL cases, scores retrieved chunks, aggregates metrics, and renders reports. |
| `rag/__init__.py` | Re-exports the public RAG seam. |

## `frontend/` — Vite + React + TypeScript

| Path | What it is |
| --- | --- |
| `frontend/package.json` | `dev` / `build` / `lint` (tsc-only) / `test` / `preview` scripts. |
| `frontend/vite.config.ts` | Vite config (React plugin). |
| `frontend/tsconfig*.json` | TypeScript project refs. |
| `frontend/.env.local` | (gitignored) — `VITE_API_BASE_URL`, `VITE_LIVEKIT_URL`. |
| `frontend/.env.example` | Template for above. |
| `frontend/src/data/embeddingEval.generated.json` | Generated embedding comparison report consumed by the eval dashboard. Update via `scripts.eval_retrieval --frontend-output`. |
| `frontend/src/data/chunkingEval.generated.json` | Generated chunking comparison report consumed by the eval dashboard. Update via `scripts.eval_chunking --frontend-output`. |
| `frontend/src/data/structuredEval.generated.json` | Generated structured lookup comparison report consumed by the eval dashboard. Update via `scripts.eval_structured --frontend-output`. |

### `frontend/src/`

| Path | What it is |
| --- | --- |
| `src/main.tsx` | React entry — mounts `<App />` into the root. |
| `src/App.tsx` | `react-router-dom` shell — `/` → Upload, `/session` → Session. |
| `src/vite-env.d.ts` | Vite/TS environment types. |
| `src/lib/api.ts` | **Only place that calls `fetch()`.** `uploadPdf`, `ingestDocument`, `listDocuments`, `documentFileUrl`, `requestToken`. |
| `src/data/retrievalEval.ts` | Normalizes generated backend eval JSON into dashboard-friendly TypeScript types. |
| `src/lib/useTypewriter.ts` | Hook used by the transcript bubbles. |
| `src/pages/UploadPage.tsx` | Landing page — `<PdfDropZone>` + uploaded-doc list. |
| `src/pages/SessionPage.tsx` | Wraps `<LiveKitRoom>` + `useVoiceAssistant` + visualizer + transcript. |
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
