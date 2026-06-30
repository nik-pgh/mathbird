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

## Testing the agent (no voice)

Two ways to exercise the full LLM + tools pipeline without mic, speaker, or
a LiveKit room participant:

**Interactive text console** — type student turns with readable tutor output
(Claude Code–style labels, tool-call summaries, no JSON debug noise):

```bash
cd backend
uv run python -m scripts.agent_console
```

Optional doc/progress scope. If `SIM_ACTIVE_DOC_ID` / `SIM_USER_ID` are unset,
the console lists uploaded PDFs and known auth users and prompts on stdin.
Set `SIM_INTERACTIVE=false` to skip prompts (or pre-set `SIM_*` in `.env`):

```bash
SIM_ACTIVE_DOC_ID=your-doc-id SIM_USER_ID=test-user \
  uv run python -m scripts.agent_console
```

Legacy LiveKit CLI console (still works; may show structured debug logs):

```bash
uv run python -m app.agent.main console --text
```

**Scripted YAML scenarios** — replay multi-turn conversations with assertions:

```bash
uv run python -m scripts.simulate_conversation \
  simulations/scenarios/tutor_greeting.yaml -v

SIM_ACTIVE_DOC_ID=your-doc-id uv run python -m scripts.simulate_conversation \
  simulations/scenarios/problem_help.yaml -v
```

Scenarios live under `simulations/scenarios/`. Each turn can assert tool calls,
`search_documents` query fragments, and assistant reply content. Fast unit tests
(no LLM): `uv run pytest tests/simulation/ -m "not live"`. Full stack against
OpenAI: `uv run pytest tests/simulation/ -m live`.

Session wiring is shared between the worker entrypoint and the simulator via
`app/agent/session_factory.py`.

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

Then upload a PDF through `POST /api/documents`; the upload route stores the PDF and
returns `status="uploaded"`. Call `POST /api/documents/{doc_id}/ingest` to run the
active retriever's `ingest_pdf` synchronously. If ingestion fails, the route returns
502 and preserves the stored PDF so it can be retried without re-uploading.

## Retrieval evaluation

After ingesting the same document into multiple embedding collections with
`scripts.ingest_all_embeddings`, run the golden retrieval evaluator:

```bash
cd backend
uv run python -m scripts.eval_retrieval --golden evals/golden/goodfellow_ch2_retrieval.jsonl --top-k 5
```

By default this evaluates the six embedding targets from
`app.rag.multi_ingest.DEFAULT_EMBEDDING_TARGETS`. Use repeated `--target
provider:model` flags to evaluate a subset. Reports are written to
`backend/evals/results/` as JSON and Markdown. If one target fails, for example
because its Qdrant collection is missing, the evaluator records that target under
`failures`, continues with the remaining targets, writes the reports, and exits
non-zero.

## Agent persona

The system prompt is loaded from a YAML file, not an env var. The default is
`backend/personas/default.yaml`, a math-tutor persona; the file must define a
non-empty top-level `instructions:` string. To swap personas without code
changes:

```bash
PERSONA_FILE=./personas/my-persona.yaml
```

`Settings.agent_instructions` is a read-only property that calls
`_load_persona()` (cached). Restart the worker after editing the YAML.

## Whiteboards

`app/agent/whiteboard/` is a pluggable handwriting-recognition + per-room state
surface that runs alongside the voice pipeline. On every room join, the
entrypoint installs a `user_board` data-channel listener and attaches a
`BoardState` to `AgentSession.userdata`; a `WhiteboardAgent` subclass then
injects the latest student-board reading into the LLM's chat context per turn.
The LLM can call `read_user_board` mid-tool-chain. AiBoard writes are driven by
the per-sentence board extractor in `WhiteboardAgent`, not exposed as direct LLM
tools.

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

Start the Phoenix UI (deps are installed by `uv sync`):

```bash
cd backend
uv run phoenix serve            # opens http://localhost:6006
```

Add these env vars (off by default — production stays untouched):

```bash
# Backend observability (Arize Phoenix)
PHOENIX_ENABLED=true
PHOENIX_PROJECT=mathbird
PHOENIX_ENDPOINT=                 # blank = local Phoenix; Cloud = https://app.phoenix.arize.com/s/<space-name>
PHOENIX_API_KEY=                  # required for Phoenix Cloud
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
it unset) makes `setup_phoenix()` a no-op — no spans exported.
