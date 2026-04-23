"""Build the python-telegram-bot Application (webhook mode, no Updater)."""

from __future__ import annotations

import logging
import os

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.bot import db
from app.bot.callbacks import callback_handlers
from app.bot.guardian import guardian_handlers
from app.bot.lab_intake import handle_lab_document
from app.bot.onboarding import build_conversation_handler
from app.bot.scheduler import unschedule_chat
from app.bot.strings import get_string
from app.bot.voice_agent import handle_ai_message, handle_voice_message

logger = logging.getLogger(__name__)


# ---------- /status ----------


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    profile = await db.get_profile(chat_id)
    if not profile:
        await update.message.reply_text(get_string("unknown_message", "hi"))  # type: ignore[union-attr]
        return

    lang = str(profile.get("language") or "hi")
    meds = await db.get_medications(chat_id)
    events = await db.get_med_events_today(chat_id)
    expected = sum(len(m.get("timings") or []) for m in meds)
    taken = sum(1 for e in events if e.get("event") == "taken")
    skipped = sum(1 for e in events if e.get("event") == "skipped")
    missed = max(expected - taken - skipped, 0)

    conditions: list[str] = list(profile.get("conditions") or [])
    conditions_text = (
        ", ".join(get_string(f"condition_{c}", lang) for c in conditions) if conditions else "—"
    )

    await update.message.reply_text(  # type: ignore[union-attr]
        get_string(
            "status_reply",
            lang,
            name=str(profile.get("name") or ""),
            conditions=conditions_text,
            med_count=len(meds),
            taken=taken,
            skipped=skipped,
            missed=missed,
        ),
        parse_mode=ParseMode.MARKDOWN,
    )


# ---------- /reset (DEBUG only) ----------


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    profile = await db.get_profile(chat_id)
    lang = str((profile or {}).get("language") or "hi")

    unschedule_chat(context.application, chat_id)
    await db.delete_medications_for_chat(chat_id)
    await db.delete_profile(chat_id)
    context.user_data.clear()  # type: ignore[union-attr]

    await update.message.reply_text(  # type: ignore[union-attr]
        get_string("reset_done", lang), parse_mode=ParseMode.MARKDOWN
    )


# ---------- unknown text ----------


async def unknown_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    profile = await db.get_profile(chat_id)
    lang = str((profile or {}).get("language") or "hi")
    await update.message.reply_text(  # type: ignore[union-attr]
        get_string("unknown_message", lang), parse_mode=ParseMode.MARKDOWN
    )


# ---------- builder ----------


def build_application(token: str, *, with_updater: bool = False) -> Application:  # type: ignore[type-arg]
    """Build the PTB Application.

    with_updater=False (default): webhook mode — FastAPI drives update delivery via
    POST /telegram/{token}. PTB's Updater is disabled.
    with_updater=True: polling mode — run_polling() pulls updates itself. Use from
    scripts/run_polling.py for local dev.
    """
    builder = (
        Application.builder()
        .token(token)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
    )
    if not with_updater:
        builder = builder.updater(None)

    app: Application = builder.build()  # type: ignore[type-arg]

    app.add_handler(build_conversation_handler())
    for h in callback_handlers():
        app.add_handler(h)
    for h in guardian_handlers():
        app.add_handler(h)
    app.add_handler(CommandHandler("status", status_cmd))
    if os.getenv("DEBUG", "false").lower() == "true":
        app.add_handler(CommandHandler("reset", reset_cmd))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_lab_document))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_ai_message))

    return app
