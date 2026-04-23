# syntax=docker/dockerfile:1.7

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:/root/.local/bin:${PATH}"

# System deps — ffmpeg for voice-note OGG conversion, libpq for psycopg/asyncpg,
# curl for uv installer + healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
        ca-certificates \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast, deterministic)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

# Install deps first for layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Now copy the app
COPY . .

# Railway injects PORT — default 8080 for local/compose parity
ENV PORT=8080
EXPOSE 8080

# Migrate + serve. Migration is idempotent (alembic tracks revisions in DB).
CMD ["sh", "-c", "uv run alembic upgrade head && exec uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
