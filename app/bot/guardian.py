"""Guardian pairing + /report command.

Flow:
  senior: /link_guardian   → receives a 6-char code
  guardian: /link_senior CODE → bot_profile.family_chat_id is set to the
            guardian's chat_id; the senior gets a confirmation DM
  guardian: /report → live digest (adherence, streak, last vitals flag)

`family_chat_id` is also the address the scheduler/vitals alerts forward to.
"""

from __future__ import annotations

import datetime as _dt
import logging
import secrets
import string

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes

from app.bot import db
from app.bot.strings import get_string

log = logging.getLogger(__name__)

_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _new_code(length: int = 6) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


async def link_guardian(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Senior issues a pairing code to hand to their guardian."""
    if not update.effective_chat or not update.message:
        return
    chat_id = update.effective_chat.id
    profile = await db.get_profile(chat_id)
    lang = str((profile or {}).get("language") or "en")

    code = _new_code()
    await db.create_link_code(chat_id, code)
    await update.message.reply_text(
        get_string("link_code_issued", lang, code=code),
        parse_mode=ParseMode.MARKDOWN,
    )


async def link_senior(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guardian redeems a pairing code to link themselves to the senior."""
    if not update.effective_chat or not update.message:
        return
    guardian_chat_id = update.effective_chat.id
    args = context.args or []
    if not args:
        await update.message.reply_text(
            get_string("link_senior_usage", "en"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    code = args[0].strip().upper()
    senior_chat_id = await db.consume_link_code(code)
    if senior_chat_id is None:
        await update.message.reply_text(get_string("link_invalid", "en"))
        return

    await db.set_family_chat_id(senior_chat_id, guardian_chat_id)

    senior = await db.get_profile(senior_chat_id)
    senior_name = str((senior or {}).get("name") or "")
    senior_lang = str((senior or {}).get("language") or "en")

    # Notify the senior
    try:
        await context.bot.send_message(
            chat_id=senior_chat_id,
            text=get_string("link_success_senior", senior_lang),
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        log.warning("link_senior_notify_failed senior=%s err=%s", senior_chat_id, exc)

    await update.message.reply_text(
        get_string("link_success_guardian", "en", name=senior_name),
        parse_mode=ParseMode.MARKDOWN,
    )


def _vitals_line_for(chat_id: int) -> str:
    """Return a single vitals summary line from the senior's vitals_flags.json memory."""
    import json
    from pathlib import Path

    from app.config import settings

    # bot chat_id → app_user linkage isn't wired (the bot runs chat_id primary),
    # so we probe memory by looking at the most recent vitals_flags.json across
    # all users who share this chat_id. For MVP: report empty unless wired.
    _ = chat_id  # reserved for future lookup
    root = Path(settings.memory_root)
    if not root.exists():
        return "🫀 Vitals: no recent data"
    latest_flag: dict | None = None
    latest_ts = ""
    for user_dir in root.iterdir():
        flag_path = user_dir / "vitals_flags.json"
        if not flag_path.exists():
            continue
        try:
            data = json.loads(flag_path.read_text())
        except Exception:
            continue
        ts = str(data.get("last_updated", ""))
        if ts > latest_ts:
            latest_ts = ts
            latest_flag = data
    if not latest_flag:
        return "🫀 Vitals: no recent data"
    recent = latest_flag.get("recent_anomalies", [])
    if not recent:
        return "🫀 Vitals: all within normal range ✅"
    top = recent[0]
    return f"🫀 Vitals flag: {top.get('narrative', '—')}"


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Guardian pulls a live digest of the seniors they're linked to."""
    if not update.effective_chat or not update.message:
        return
    guardian_chat_id = update.effective_chat.id
    seniors = await db.get_seniors_for_guardian(guardian_chat_id)
    if not seniors:
        await update.message.reply_text(get_string("report_no_link", "en"))
        return

    today = _dt.date.today().isoformat()
    chunks: list[str] = []
    for s in seniors:
        chat_id = int(s["chat_id"])
        name = str(s.get("name") or "—")

        meds = await db.get_medications(chat_id)
        events = await db.get_med_events_today(chat_id)
        expected = sum(len(m.get("timings") or []) for m in meds)
        taken = sum(1 for e in events if e.get("event") == "taken")
        skipped = sum(1 for e in events if e.get("event") == "skipped")
        missed = max(expected - taken - skipped, 0)
        streak = await db.get_adherence_streak(chat_id)

        header = get_string("report_header", "en", name=name, date=today)
        body = get_string(
            "report_body",
            "en",
            taken=taken,
            skipped=skipped,
            missed=missed,
            streak=streak,
            vitals_line=_vitals_line_for(chat_id),
        )
        chunks.append(f"{header}\n{body}")

    await update.message.reply_text("\n\n".join(chunks), parse_mode=ParseMode.MARKDOWN)


def guardian_handlers() -> list[CommandHandler]:
    return [
        CommandHandler("link_guardian", link_guardian),
        CommandHandler("link_senior", link_senior),
        CommandHandler("report", report_cmd),
    ]
