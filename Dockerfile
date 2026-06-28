# ─── Builder stage ────────────────────────────────────────────────────────────
# Installs all backend deps into a venv via uv, then copies source.

FROM python:3.11-slim AS builder

# System build deps needed by some wheels (onnxruntime, scipy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app/backend

# Copy dependency manifest first for layer caching.
# uv.lock is gitignored, so we let uv resolve here.
COPY backend/pyproject.toml backend/.python-version ./
RUN uv sync --no-cache

# Copy the rest of the source
COPY backend/ .

# ─── Runtime stage ────────────────────────────────────────────────────────────
# Slim image with only runtime libs + the venv from builder.

FROM python:3.11-slim

# Runtime system deps:
#   libgomp1  — OpenMP (numpy/scipy/onnxruntime)
#   ffmpeg    — audio codec support for livekit-agents
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the resolved venv and application source
COPY --from=builder /app/backend /app/backend

WORKDIR /app/backend

# Activate the venv
ENV PATH="/app/backend/.venv/bin:$PATH"
ENV VIRTUAL_ENV="/app/backend/.venv"
ENV PYTHONUNBUFFERED=1

# The .env file is expected at the repo root (one level up from backend/).
# Settings reads both ./backend/.env and ../.env (repo root).
# In production, inject env vars directly via the platform (fly secrets, etc.).
# If you need a root .env, mount it at /app/.env.
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

# Default: run the HTTP API. Override CMD to start the worker instead.
#
#   API:     docker run mathbird-backend
#   Worker:  docker run mathbird-backend python -m app.agent.main start
#
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
