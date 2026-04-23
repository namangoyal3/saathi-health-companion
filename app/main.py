"""FastAPI application entry point."""

from __future__ import annotations

import subprocess
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update

from app.api.chat import router as chat_router
from app.api.ivr import router as ivr_router
from app.api.labs import router as labs_router
from app.api.wearable import router as wearable_router
from app.bot import db as bot_db
from app.bot.application import build_application
from app.bot.scheduler import schedule_all_on_startup
from app.config import settings
from app.db.session import get_db

log = structlog.get_logger(__name__)

_ptb_app: Any = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    global _ptb_app

    await bot_db.init_pool()

    if settings.telegram_bot_token:
        _ptb_app = build_application(settings.telegram_bot_token)
        try:
            await _ptb_app.initialize()
            await _ptb_app.start()
            await schedule_all_on_startup(_ptb_app)
            log.info("Telegram bot initialized")
        except Exception as exc:
            log.warning("Telegram bot init failed — updates will queue", error=str(exc))
    else:
        log.warning("TELEGRAM_BOT_TOKEN not set — bot disabled")

    yield

    if _ptb_app is not None:
        try:
            await _ptb_app.stop()
            await _ptb_app.shutdown()
        except Exception:
            pass
    await bot_db.close_pool()


app = FastAPI(
    title="Saath",
    description="AI health companion for aging Indian parents and their NRI children.",
    version="0.1.0",
    docs_url="/docs" if settings.environment != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(labs_router)
app.include_router(ivr_router)
app.include_router(wearable_router)


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


@app.post("/telegram/{token}")
async def telegram_webhook(token: str, request: Request) -> dict[str, str]:
    """Receive Telegram updates. Token in path guards against spoofing."""
    if not settings.telegram_bot_token or token != settings.telegram_bot_token:
        raise HTTPException(status_code=403, detail="forbidden")

    if _ptb_app is None:
        raise HTTPException(status_code=503, detail="bot not initialized")

    try:
        data = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid json") from exc

    update = Update.de_json(data, _ptb_app.bot)
    if update is not None:
        await _ptb_app.process_update(update)

    return {"ok": "true"}
