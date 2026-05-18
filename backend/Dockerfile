# LiveKit Cloud Agents image for the mathbird voice agent worker.
# Build context is `backend/` (frontend and root files are excluded by
# `.dockerignore`). The HTTP API process is NOT deployed here — it ships
# separately on a general web host. Only the long-running agent worker
# (`python -m app.agent.main start`) runs in this container.

FROM python:3.11-slim

# uv binary used for fast, deterministic dependency installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

# Copy project metadata + source. We intentionally install with the
# `observability` extra so the worker can emit traces to Phoenix Cloud.
COPY pyproject.toml ./
COPY app/ ./app/
COPY personas/ ./personas/

RUN uv pip install -e ".[observability]"

# Prewarm plugin models (Silero VAD weights, turn-detector ONNX, etc.) at
# build time so the first session in production isn't bottlenecked on a
# cold download.
RUN python -m app.agent.main download-files

# Run as a non-root user.
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

# LiveKit Cloud Agents invokes the container directly; `start` runs the
# production worker (no auto-reload, no dev server).
CMD ["python", "-m", "app.agent.main", "start"]
