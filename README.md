<p align="center">
  <img src="./docs/assets/mathbird-logo.svg" alt="Mathbird logo" width="360">
</p>

# Mathbird

Mathbird is a voice-based math tutor. Students upload a PDF, join a LiveKit
voice room, and talk with an AI agent that can answer from the uploaded
material. The app also includes shared whiteboards so the agent can show math
work and the student can draw or write during the session.

On-the-fly demo: https://mathbird.vercel.app/

The project has two parts:

- `backend/`: Python FastAPI app plus a LiveKit agent worker.
- `frontend/`: Vite, React, and TypeScript web app.

LiveKit Cloud handles the realtime room. You do not run a LiveKit server
locally.

## Design Document

### End-to-end flow

1. The student opens the React app and uploads a PDF.
2. The frontend sends the PDF to the FastAPI backend with `POST /api/documents`.
3. The backend stores the file and, when RAG is enabled, indexes it for search.
4. The student starts a voice session.
5. The frontend asks the backend for a LiveKit token with `POST /api/token`.
6. The frontend joins a LiveKit Cloud room using that token.
7. The LiveKit agent worker is dispatched into the room.
8. The worker runs the voice pipeline:
   - speech-to-text turns student audio into text
   - the LLM decides how to respond and can call tools
   - text-to-speech streams the answer back into the room
9. When the student asks about the uploaded PDF, the agent can call the
   document search tool before answering.

The backend is split into two running processes:

- FastAPI HTTP API: uploads PDFs and issues LiveKit access tokens.
- LiveKit agent worker: joins rooms and runs the STT -> LLM -> TTS loop.

Both processes share the same settings, storage, RAG, and provider interfaces.

### RAG integration

RAG is integrated through a small `Retriever` interface in `backend/app/rag`.
That interface supports two actions:

- `ingest_pdf(...)`: parse and index a newly uploaded PDF.
- `retrieve(...)`: search indexed document chunks during a conversation.

The default setting is `RAG_PROVIDER=null`, which makes uploads and retrieval
no-ops. This keeps the app easy to run locally without Qdrant or LlamaParse.

To enable real textbook retrieval, set:

```bash
RAG_PROVIDER=llamaindex_qdrant
LLAMAPARSE_API_KEY=...
OPENAI_API_KEY=...
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=mathbird_documents
```

With that provider enabled:

1. Uploaded PDFs are parsed with LlamaParse.
2. Parsed content is normalized into page-aware textbook chunks.
3. LlamaIndex embeds and indexes those chunks into Qdrant.
4. During a voice session, the agent calls `search_documents`.
5. Retrieved chunks are returned with citations and used to ground the answer.

### Tools and frameworks

Backend:

- Python 3.11+
- FastAPI for the HTTP API
- LiveKit Agents for realtime voice agent sessions
- Pydantic and pydantic-settings for typed config
- LlamaParse, LlamaIndex, OpenAI embeddings, and Qdrant for RAG
- Local filesystem or S3 for PDF storage
- Optional Arize Phoenix tracing for LLM, RAG, and tool-call observability

Frontend:

- Vite
- React
- TypeScript
- LiveKit React components
- KaTeX for rendering math
- DOMPurify for safe SVG/HTML rendering
- perfect-freehand for the drawing canvas

Voice provider options are configured by environment variables. The current
setup supports Deepgram or OpenAI for STT, OpenAI for the LLM, Cartesia,
ElevenLabs, or OpenAI for TTS, and Silero for VAD.

## Setup

### Prerequisites

- Python 3.11+
- `uv` for backend dependency management
- Node.js and npm
- A LiveKit Cloud project
- API keys for the providers you choose in `.env`
- Docker, only if you want to run Qdrant locally for RAG

### 1. Configure environment variables

Copy the root environment template:

```bash
cp .env.example .env
```

Fill in the LiveKit values from your LiveKit Cloud project:

```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...
```

Then add provider keys for the selected stack, for example:

```bash
DEEPGRAM_API_KEY=...
OPENAI_API_KEY=...
CARTESIA_API_KEY=...
```

Copy the frontend environment template:

```bash
cp frontend/.env.example frontend/.env.local
```

For local development, use:

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_LIVEKIT_URL=wss://your-project.livekit.cloud
```

### 2. Start the backend API

In the first terminal:

```bash
cd backend
uv sync
uv run uvicorn app.api.main:app --reload --port 8000
```

### 3. Start the LiveKit agent worker

In the second terminal:

```bash
cd backend
uv run python -m app.agent.main dev
```

The worker connects to LiveKit Cloud and waits for room dispatches.

### 4. Start the frontend

In the third terminal:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Upload a PDF, start a conversation, and speak to the agent.

### Optional: run Qdrant for local RAG

```bash
docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant
```

Then enable the `llamaindex_qdrant` RAG provider in `.env` as shown above.

### Running on the web

For a hosted deployment, run the same three pieces:

- FastAPI backend as a web service.
- LiveKit agent worker as a long-running worker process.
- Frontend as a static Vite build.

Set `VITE_API_BASE_URL` to the deployed backend URL and keep `VITE_LIVEKIT_URL`
pointed at the same LiveKit Cloud project used by the backend and worker.

## Additional Features

### Whiteboards

Mathbird has two LiveKit data-channel whiteboards:

- The AI board shows the agent's work, such as equations, plots, and simple
  shapes.
- The user board lets the student draw or write during the session.

The user board can be interpreted by a vision model when
`BOARD_READER=openai_vision`. The latest reading is added to the agent's
context so it can respond to what the student wrote.

The AI board can be driven by the board extractor when `BOARD_EXTRACTOR=openai`.
The extractor watches the agent's spoken sentences and publishes useful board
items without exposing direct board-writing tools to the main agent.

### Provider swapping

Most external services are selected with environment variables:

```bash
STT_PROVIDER=deepgram
LLM_PROVIDER=openai
TTS_PROVIDER=cartesia
VAD_PROVIDER=silero
STORAGE_BACKEND=local
RAG_PROVIDER=null
```

Provider-specific code lives behind factories and protocols, so the main agent
flow does not need to change when a provider changes.

### Persona

The agent prompt lives in `backend/personas/default.yaml`. To use a different
prompt, create another YAML file with an `instructions:` field and set:

```bash
PERSONA_FILE=./personas/my-persona.yaml
```

Restart the backend processes after changing persona settings.

### Storage

Uploaded PDFs are stored locally by default:

```bash
STORAGE_BACKEND=local
STORAGE_LOCAL_DIR=./uploads
```

S3 is also supported:

```bash
STORAGE_BACKEND=s3
S3_BUCKET=...
S3_REGION=...
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### Observability

Phoenix tracing is optional. When enabled, it records LLM calls, RAG retrievals,
and function-tool calls.

```bash
cd backend
uv sync --extra observability
uv run phoenix serve
```

Then set:

```bash
PHOENIX_ENABLED=true
PHOENIX_PROJECT=mathbird
# Phoenix Cloud only:
PHOENIX_ENDPOINT=https://app.phoenix.arize.com/s/<space-name>
PHOENIX_API_KEY=...
```

The Phoenix UI runs at `http://localhost:6006` by default.

### More documentation

- `docs/ARCHITECTURE.md`: deeper explanation of the backend, frontend, RAG, and
  whiteboard architecture.
- `docs/INDEX.md`: hand-maintained map of important files and modules.
- `backend/README.md`: backend-specific setup and operational notes.
