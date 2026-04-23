"""Onboarding ConversationHandler — /start and /edit flows."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytz  # type: ignore[import]
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from app.bot import db
from app.bot.strings import get_string, timing_label

logger = logging.getLogger(__name__)

LANG, NAME, CONDITIONS, MED_NAME, MED_DOSE, MED_TIMING, MED_MORE, CONFIRM = range(8)

CONDITION_KEYS = ["diabetes", "bp", "thyroid", "ckd", "heart", "other"]
TIMING_KEYS = ["morning", "afternoon", "evening", "night"]

IST = pytz.timezone("Asia/Kolkata")
TIMING_CLOCK = {
    "morning": "08:00",
    "afternoon": "13:00",
    "evening": "18:00",
    "night": "21:00",
}


# ---------- keyboards ----------


def _language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇮🇳 हिंदी", callback_data="lang_hi"),
                InlineKeyboardButton("🇮🇳 தமிழ்", callback_data="lang_ta"),
                InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            ]
        ]
    )


def _conditions_keyboard(lang: str, selected: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key in CONDITION_KEYS:
        label = get_string(f"condition_{key}", lang)
        if key in selected:
            label = f"✅ {label}"
        row.append(InlineKeyboardButton(label, callback_data=f"cond_toggle_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(get_string("done_btn", lang), callback_data="cond_done")])
    return InlineKeyboardMarkup(rows)


def _dose_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(get_string("skip_btn", lang), callback_data="med_dose_skip")]]
    )


def _timing_keyboard(lang: str, selected: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for key in TIMING_KEYS:
        label = get_string(f"timing_{key}", lang)
        if key in selected:
            label = f"✅ {label}"
        row.append(InlineKeyboardButton(label, callback_data=f"timing_toggle_{key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(get_string("done_btn", lang), callback_data="timing_done")])
    return InlineKeyboardMarkup(rows)


def _more_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(get_string("add_more_btn", lang), callback_data="more_yes"),
                InlineKeyboardButton(get_string("no_more_btn", lang), callback_data="more_no"),
            ]
        ]
    )


def _confirm_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(get_string("confirm_btn", lang), callback_data="confirm_yes"),
                InlineKeyboardButton(get_string("edit_btn", lang), callback_data="confirm_edit"),
            ]
        ]
    )


# ---------- helpers ----------


def _conditions_summary(conditions: list[str], lang: str) -> str:
    if not conditions:
        return "—"
    return ", ".join(get_string(f"condition_{c}", lang) for c in conditions)


def _timings_summary(timings: list[str], lang: str) -> str:
    if not timings:
        return "—"
    return ", ".join(timing_label(t, lang) for t in timings)


def _next_reminder_time(meds: list[dict[str, object]]) -> str:
    now = datetime.now(IST)
    candidates: list[tuple[datetime, str]] = []
    for med in meds:
        for t in med.get("timings") or []:  # type: ignore[union-attr]
            hhmm = TIMING_CLOCK.get(str(t))
            if not hhmm:
                continue
            hh, mm = (int(x) for x in hhmm.split(":"))
            dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if dt <= now:
                dt = dt + timedelta(days=1)
            candidates.append((dt, hhmm))
    if not candidates:
        return "—"
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


# ---------- entry points ----------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    profile = await db.get_profile(chat_id)
    if profile:
        lang = str(profile.get("language") or "en")
        await update.message.reply_text(  # type: ignore[union-attr]
            get_string("already_registered", lang), parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    context.user_data.clear()  # type: ignore[union-attr]
    context.user_data["meds"] = []  # type: ignore[union-attr]
    context.user_data["conditions"] = set()  # type: ignore[union-attr]
    await update.message.reply_text(  # type: ignore[union-attr]
        get_string("welcome", "hi"),
        reply_markup=_language_keyboard(),
        parse_mode=ParseMode.MARKDOWN,
    )
    return LANG


async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    profile = await db.get_profile(chat_id)
    lang = str((profile or {}).get("language") or "hi")

    context.user_data.clear()  # type: ignore[union-attr]
    context.user_data["meds"] = []  # type: ignore[union-attr]
    context.user_data["conditions"] = set()  # type: ignore[union-attr]
    context.user_data["language"] = lang  # type: ignore[union-attr]

    await update.message.reply_text(  # type: ignore[union-attr]
        get_string("ask_name", lang), parse_mode=ParseMode.MARKDOWN
    )
    return NAME


# ---------- LANG ----------


async def lang_pick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = query.data.split("_", 1)[1]  # type: ignore[union-attr]
    context.user_data["language"] = lang  # type: ignore[union-attr]
    await query.edit_message_text(  # type: ignore[union-attr]
        get_string("ask_name", lang), parse_mode=ParseMode.MARKDOWN
    )
    return NAME


# ---------- NAME ----------


async def name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    name = (update.message.text or "").strip()  # type: ignore[union-attr]
    if not name:
        await update.message.reply_text(  # type: ignore[union-attr]
            get_string("ask_name", lang), parse_mode=ParseMode.MARKDOWN
        )
        return NAME
    context.user_data["name"] = name  # type: ignore[union-attr]
    await update.message.reply_text(  # type: ignore[union-attr]
        get_string("ask_conditions", lang),
        reply_markup=_conditions_keyboard(lang, context.user_data["conditions"]),  # type: ignore[union-attr]
        parse_mode=ParseMode.MARKDOWN,
    )
    return CONDITIONS


# ---------- CONDITIONS ----------


async def conditions_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    key = query.data.replace("cond_toggle_", "")  # type: ignore[union-attr]
    selected: set[str] = context.user_data.setdefault("conditions", set())  # type: ignore[union-attr]
    if key in selected:
        selected.remove(key)
    else:
        selected.add(key)
    await query.edit_message_reply_markup(reply_markup=_conditions_keyboard(lang, selected))  # type: ignore[union-attr]
    return CONDITIONS


async def conditions_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    await query.edit_message_text(  # type: ignore[union-attr]
        get_string("ask_med_name", lang), parse_mode=ParseMode.MARKDOWN
    )
    context.user_data["current_med"] = {}  # type: ignore[union-attr]
    return MED_NAME


# ---------- MED_NAME ----------


async def med_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    drug = (update.message.text or "").strip()  # type: ignore[union-attr]
    if not drug:
        await update.message.reply_text(  # type: ignore[union-attr]
            get_string("ask_med_name", lang), parse_mode=ParseMode.MARKDOWN
        )
        return MED_NAME
    context.user_data.setdefault("current_med", {})["name"] = drug  # type: ignore[union-attr]
    await update.message.reply_text(  # type: ignore[union-attr]
        get_string("ask_med_dose", lang),
        reply_markup=_dose_keyboard(lang),
        parse_mode=ParseMode.MARKDOWN,
    )
    return MED_DOSE


# ---------- MED_DOSE ----------


async def med_dose_skip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    context.user_data.setdefault("current_med", {})["dose"] = None  # type: ignore[union-attr]
    context.user_data.setdefault("current_med", {})["_timings"] = set()  # type: ignore[union-attr]
    await query.edit_message_text(  # type: ignore[union-attr]
        get_string("ask_med_timing", lang),
        reply_markup=_timing_keyboard(lang, set()),
        parse_mode=ParseMode.MARKDOWN,
    )
    return MED_TIMING


async def med_dose_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    dose = (update.message.text or "").strip()  # type: ignore[union-attr]
    context.user_data.setdefault("current_med", {})["dose"] = dose or None  # type: ignore[union-attr]
    context.user_data["current_med"]["_timings"] = set()  # type: ignore[union-attr]
    await update.message.reply_text(  # type: ignore[union-attr]
        get_string("ask_med_timing", lang),
        reply_markup=_timing_keyboard(lang, set()),
        parse_mode=ParseMode.MARKDOWN,
    )
    return MED_TIMING


# ---------- MED_TIMING ----------


async def med_timing_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    key = query.data.replace("timing_toggle_", "")  # type: ignore[union-attr]
    med = context.user_data.setdefault("current_med", {})  # type: ignore[union-attr]
    selected: set[str] = med.setdefault("_timings", set())
    if key in selected:
        selected.remove(key)
    else:
        selected.add(key)
    await query.edit_message_reply_markup(reply_markup=_timing_keyboard(lang, selected))  # type: ignore[union-attr]
    return MED_TIMING


async def med_timing_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    med = context.user_data.get("current_med") or {}  # type: ignore[union-attr]
    timings = sorted(med.get("_timings") or set(), key=lambda t: TIMING_KEYS.index(t))
    if not timings:
        await query.edit_message_text(  # type: ignore[union-attr]
            get_string("ask_med_timing", lang),
            reply_markup=_timing_keyboard(lang, set()),
            parse_mode=ParseMode.MARKDOWN,
        )
        return MED_TIMING

    finalized: dict[str, object] = {
        "name": med["name"],
        "dose": med.get("dose"),
        "timings": timings,
    }
    context.user_data.setdefault("meds", []).append(finalized)  # type: ignore[union-attr]
    context.user_data["current_med"] = {}  # type: ignore[union-attr]

    await query.edit_message_text(  # type: ignore[union-attr]
        get_string(
            "med_added", lang, drug=str(finalized["name"]), timings=_timings_summary(timings, lang)
        ),
        reply_markup=_more_keyboard(lang),
        parse_mode=ParseMode.MARKDOWN,
    )
    return MED_MORE


# ---------- MED_MORE ----------


async def med_more_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    context.user_data["current_med"] = {}  # type: ignore[union-attr]
    await query.edit_message_text(  # type: ignore[union-attr]
        get_string("ask_med_name", lang), parse_mode=ParseMode.MARKDOWN
    )
    return MED_NAME


async def med_more_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    name = str(context.user_data.get("name") or "")  # type: ignore[union-attr]
    conditions = sorted(
        context.user_data.get("conditions") or set(),  # type: ignore[union-attr]
        key=lambda c: CONDITION_KEYS.index(c),
    )
    context.user_data["conditions_list"] = conditions  # type: ignore[union-attr]
    meds: list[dict[str, object]] = context.user_data.get("meds") or []  # type: ignore[union-attr]

    med_lines = []
    for m in meds:
        dose = f" — {m['dose']}" if m.get("dose") else ""
        timings_str = _timings_summary(list(m.get("timings") or []), lang)  # type: ignore[arg-type]
        med_lines.append(f"• *{m['name']}*{dose} ({timings_str})")

    summary = get_string(
        "confirm_profile",
        lang,
        name=name,
        conditions=_conditions_summary(conditions, lang),
        meds="\n".join(med_lines) if med_lines else "—",
    )
    await query.edit_message_text(  # type: ignore[union-attr]
        summary, reply_markup=_confirm_keyboard(lang), parse_mode=ParseMode.MARKDOWN
    )
    return CONFIRM


# ---------- CONFIRM ----------


async def confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    name = str(context.user_data.get("name") or "")  # type: ignore[union-attr]
    conditions: list[str] = context.user_data.get("conditions_list") or sorted(  # type: ignore[union-attr]
        context.user_data.get("conditions") or set(),  # type: ignore[union-attr]
        key=lambda c: CONDITION_KEYS.index(c),
    )
    meds: list[dict[str, object]] = context.user_data.get("meds") or []  # type: ignore[union-attr]

    await db.save_profile(chat_id, name, lang, conditions)
    await db.delete_medications_for_chat(chat_id)
    for m in meds:
        await db.save_medication(
            chat_id,
            str(m["name"]),
            str(m["dose"]) if m.get("dose") else None,
            None,
            list(m.get("timings") or []),  # type: ignore[arg-type]
        )

    from app.bot.scheduler import schedule_reminders_for_profile

    await schedule_reminders_for_profile(context.application, chat_id)

    db_meds = await db.get_medications(chat_id)
    next_time = _next_reminder_time(db_meds)  # type: ignore[arg-type]
    await query.edit_message_text(  # type: ignore[union-attr]
        get_string("onboarding_done", lang, next_time=next_time), parse_mode=ParseMode.MARKDOWN
    )

    context.user_data.clear()  # type: ignore[union-attr]
    return ConversationHandler.END


async def confirm_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # type: ignore[union-attr]
    lang = str(context.user_data.get("language") or "hi")  # type: ignore[union-attr]
    context.user_data["meds"] = []  # type: ignore[union-attr]
    context.user_data["conditions"] = set()  # type: ignore[union-attr]
    await query.edit_message_text(  # type: ignore[union-attr]
        get_string("ask_name", lang), parse_mode=ParseMode.MARKDOWN
    )
    return NAME


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()  # type: ignore[union-attr]
    return ConversationHandler.END


# ---------- builder ----------


def build_conversation_handler() -> ConversationHandler:  # type: ignore[type-arg]
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("edit", edit_cmd),
        ],
        states={
            LANG: [CallbackQueryHandler(lang_pick, pattern=r"^lang_(hi|ta|en)$")],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_received)],
            CONDITIONS: [
                CallbackQueryHandler(conditions_toggle, pattern=r"^cond_toggle_"),
                CallbackQueryHandler(conditions_done, pattern=r"^cond_done$"),
            ],
            MED_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, med_name_received)],
            MED_DOSE: [
                CallbackQueryHandler(med_dose_skip, pattern=r"^med_dose_skip$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, med_dose_text),
            ],
            MED_TIMING: [
                CallbackQueryHandler(med_timing_toggle, pattern=r"^timing_toggle_"),
                CallbackQueryHandler(med_timing_done, pattern=r"^timing_done$"),
            ],
            MED_MORE: [
                CallbackQueryHandler(med_more_yes, pattern=r"^more_yes$"),
                CallbackQueryHandler(med_more_no, pattern=r"^more_no$"),
            ],
            CONFIRM: [
                CallbackQueryHandler(confirm_yes, pattern=r"^confirm_yes$"),
                CallbackQueryHandler(confirm_edit, pattern=r"^confirm_edit$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        name="onboarding",
        persistent=False,
    )
