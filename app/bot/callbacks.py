"""Inline keyboard callback handlers: took / snooze / skip."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, ContextTypes

from app.bot import db
from app.bot.scheduler import build_reminder_id, schedule_snooze
from app.bot.strings import get_string, timing_label

logger = logging.getLogger(__name__)

SNOOZE_LIMIT = 2


def _parse(cb_data: str) -> tuple[str, str, str]:
    """`took_{uuid}_{timing}` → (action, uuid, timing). UUIDs contain no '_'."""
    action, rest = cb_data.split("_", 1)
    uuid, timing = rest.rsplit("_", 1)
    return action, uuid, timing


async def _resolve_drug_name(med_id: str) -> str:
    med = await db.get_medication(med_id)
    return str(med["drug_name"]) if med else "—"


# ---------- took ----------


async def handle_took(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    _, med_id, timing = _parse(query.data)  # type: ignore[union-attr]

    profile = await db.get_profile(chat_id)
    lang = str((profile or {}).get("language") or "hi")
    drug_name = await _resolve_drug_name(med_id)
    reminder_id = build_reminder_id(chat_id, med_id, timing)

    await db.save_med_event(chat_id, med_id, drug_name, "taken", reminder_id, timing)
    await db.clear_snooze_count(reminder_id)

    try:
        await query.edit_message_text(  # type: ignore[union-attr]
            get_string("took_confirm", lang), parse_mode=ParseMode.MARKDOWN
        )
    except Exception as exc:
        logger.debug("edit_message_text failed: %s", exc)


# ---------- snooze ----------


async def handle_snooze(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    _, med_id, timing = _parse(query.data)  # type: ignore[union-attr]

    profile = await db.get_profile(chat_id)
    lang = str((profile or {}).get("language") or "hi")
    drug_name = await _resolve_drug_name(med_id)
    reminder_id = build_reminder_id(chat_id, med_id, timing)

    count = await db.get_snooze_count(reminder_id)

    if count >= SNOOZE_LIMIT:
        await db.save_med_event(chat_id, med_id, drug_name, "skipped", reminder_id, timing)
        await db.clear_snooze_count(reminder_id)
        try:
            await query.edit_message_text(  # type: ignore[union-attr]
                get_string("snooze_exhausted", lang), parse_mode=ParseMode.MARKDOWN
            )
        except Exception as exc:
            logger.debug("edit_message_text failed: %s", exc)
        return

    await db.increment_snooze_count(reminder_id, chat_id)
    schedule_snooze(context.application, chat_id, med_id, drug_name, timing, minutes=30)

    try:
        await query.edit_message_text(  # type: ignore[union-attr]
            get_string("snooze_confirm", lang), parse_mode=ParseMode.MARKDOWN
        )
    except Exception as exc:
        logger.debug("edit_message_text failed: %s", exc)


# ---------- skip ----------


async def handle_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    _, med_id, timing = _parse(query.data)  # type: ignore[union-attr]

    profile = await db.get_profile(chat_id)
    lang = str((profile or {}).get("language") or "hi")
    drug_name = await _resolve_drug_name(med_id)
    reminder_id = build_reminder_id(chat_id, med_id, timing)

    await db.save_med_event(chat_id, med_id, drug_name, "skipped", reminder_id, timing)
    await db.clear_snooze_count(reminder_id)

    try:
        await query.edit_message_text(  # type: ignore[union-attr]
            get_string("skip_confirm", lang, timing=timing_label(timing, lang)),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        logger.debug("edit_message_text failed: %s", exc)


# ---------- registration ----------


def callback_handlers() -> list[CallbackQueryHandler]:  # type: ignore[type-arg]
    return [
        CallbackQueryHandler(handle_took, pattern=r"^took_"),
        CallbackQueryHandler(handle_snooze, pattern=r"^snooze_"),
        CallbackQueryHandler(handle_skip, pattern=r"^skip_"),
    ]
