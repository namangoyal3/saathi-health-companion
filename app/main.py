"""FastAPI application entry point."""

from __future__ import annotations

import subprocess
from typing import Any

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db

log = structlog.get_logger(__name__)

app = FastAPI(
    title="Saath",
    description="AI health companion for aging Indian parents and their NRI children.",
    version="0.1.0",
    docs_url="/docs" if settings.environment != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:  # noqa: B008
    """Liveness + readiness probe. Returns git SHA and configured model IDs."""
    await db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "version": _git_sha(),
        "models": {
            "opus": settings.model_opus,
            "haiku": settings.model_haiku,
        },
        "environment": settings.environment,
    }
