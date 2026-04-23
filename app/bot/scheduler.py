"""APScheduler reminder jobs, daily summary, startup loader."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

import pytz  # type: ignore[import]
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import]
from apscheduler.triggers.cron import CronTrigger  # type: ignore[import]
from apscheduler.triggers.date import DateTrigger  # type: ignore[import]
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import Application

from app.bot import db
from app.bot.strings import get_string, timing_label

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

TIMING_CLOCK: dict[str, tuple[int, int]] = {
    "morning": (8, 0),
    "afternoon": (13, 0),
    "evening": (18, 0),
    "night": (21, 0),
}

DAILY_SUMMARY_HOUR = 22
DAILY_SUMMARY_MIN = 30


# ---------- scheduler lifecycle ----------


def init_scheduler(app: Application) -> AsyncIOScheduler:  # type: ignore[return]
    scheduler: AsyncIOScheduler | None = app.bot_data.get("scheduler")
    if scheduler is None:
        scheduler = AsyncIOScheduler(timezone=IST)
        app.bot_data["scheduler"] = scheduler
    return scheduler


async def schedule_all_on_startup(app: Application) -> None:
    """On bot boot: load every profile and (re)schedule all reminders + daily summary."""
    scheduler = init_scheduler(app)

    if not scheduler.get_job("daily_summary"):
        scheduler.add_job(
            daily_summary_job,
            trigger=CronTrigger(hour=DAILY_SUMMARY_HOUR, minute=DAILY_SUMMARY_MIN, timezone=IST),
            id="daily_summary",
            args=[app],
            replace_existing=True,
        )

    if not scheduler.running:
        scheduler.start()

    profiles = await db.get_all_profiles()
    for profile in profiles:
        await schedule_reminders_for_profile(app, int(profile["chat_id"]))

    logger.info("Scheduled reminders for %d profiles", len(profiles))


# ---------- per-profile scheduling ----------


async def schedule_reminders_for_profile(app: Application, chat_id: int) -> None:
    scheduler = init_scheduler(app)
    if not scheduler.running:
        scheduler.start()

    prefix = f"rem_{chat_id}_"
    for job in list(scheduler.get_jobs()):
        if job.id.startswith(prefix):
            job.remove()

    meds = await db.get_medications(chat_id)
    for med in meds:
        med_id = str(med["id"])
        drug_name = str(med["drug_name"])
        for timing in med.get("timings") or []:
            hhmm = TIMING_CLOCK.get(str(timing))
            if not hhmm:
                continue
            hour, minute = hhmm
            job_id = f"rem_{chat_id}_{med_id}_{timing}"
            scheduler.add_job(
                send_reminder,
                trigger=CronTrigger(hour=hour, minute=minute, timezone=IST),
                id=job_id,
                args=[app, chat_id, med_id, drug_name, timing],
                replace_existing=True,
            )


def unschedule_chat(app: Application, chat_id: int) -> None:
    scheduler = init_scheduler(app)
    prefix = f"rem_{chat_id}_"
    for job in list(scheduler.get_jobs()):
        if job.id.startswith(prefix) or job.id.startswith(f"snooze_{chat_id}_"):
            job.remove()


# ---------- sending reminders ----------


def build_reminder_id(chat_id: int, med_id: str, timing: str, for_date: date | None = None) -> str:
    for_date = for_date or date.today()
    return f"{chat_id}_{med_id}_{timing}_{for_date.isoformat()}"


def _reminder_keyboard(med_id: str, timing: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    get_string("took_btn", lang), callback_data=f"took_{med_id}_{timing}"
                )
            ],
            [
                InlineKeyboardButton(
                    get_string("snooze_btn", lang), callback_data=f"snooze_{med_id}_{timing}"
                )
            ],
            [
                InlineKeyboardButton(
                    get_string("skip_btn_reminder", lang), callback_data=f"skip_{med_id}_{timing}"
                )
            ],
        ]
    )


async def send_reminder(
    app: Application, chat_id: int, med_id: str, drug_name: str, timing: str
) -> None:
    profile = await db.get_profile(chat_id)
    if not profile:
        return
    lang = str(profile.get("language") or "hi")
    name = str(profile.get("name") or "")

    text = get_string(
        "reminder_header", lang, name=name, drug=drug_name, timing=timing_label(timing, lang)
    )
    try:
        await app.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=_reminder_keyboard(med_id, timing, lang),
        )
    except Exception as exc:
        logger.warning("send_reminder failed for %s: %s", chat_id, exc)


# ---------- snooze rescheduling ----------


def schedule_snooze(
    app: Application, chat_id: int, med_id: str, drug_name: str, timing: str, minutes: int = 30
) -> None:
    scheduler = init_scheduler(app)
    if not scheduler.running:
        scheduler.start()
    run_at = datetime.now(IST) + timedelta(minutes=minutes)
    job_id = f"snooze_{chat_id}_{med_id}_{timing}_{int(run_at.timestamp())}"
    scheduler.add_job(
        send_reminder,
        trigger=DateTrigger(run_date=run_at, timezone=IST),
        id=job_id,
        args=[app, chat_id, med_id, drug_name, timing],
        replace_existing=True,
    )


# ---------- daily summary ----------


async def daily_summary_job(app: Application) -> None:
    profiles = await db.get_all_profiles()
    for profile in profiles:
        try:
            await _send_summary_for_profile(app, profile)
        except Exception as exc:
            logger.warning("daily summary failed for %s: %s", profile.get("chat_id"), exc)


async def _send_summary_for_profile(app: Application, profile: dict[str, Any]) -> None:
    chat_id = int(profile["chat_id"])
    lang = str(profile.get("language") or "hi")

    meds = await db.get_medications(chat_id)
    expected_doses = sum(len(m.get("timings") or []) for m in meds)
    if expected_doses == 0:
        return

    events = await db.get_med_events_today(chat_id)
    taken = sum(1 for e in events if e.get("event") == "taken")
    skipped = sum(1 for e in events if e.get("event") == "skipped")
    missed = max(expected_doses - taken - skipped, 0)
    streak = await db.get_adherence_streak(chat_id)

    header = get_string("daily_summary_header", lang, date=date.today().isoformat())
    body_lines = [
        get_string("daily_summary_taken", lang, count=taken),
        get_string("daily_summary_skipped", lang, count=skipped),
        get_string("daily_summary_missed", lang, count=missed),
    ]
    if streak >= 2:
        body_lines.append(get_string("streak_line", lang, streak=streak))
    text = f"{header}\n" + "\n".join(body_lines)

    try:
        await app.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
    except Exception as exc:
        logger.warning("daily summary send failed for %s: %s", chat_id, exc)

    # Forward to guardian if linked
    family_chat_id = profile.get("family_chat_id")
    if family_chat_id:
        name = str(profile.get("name") or "")
        try:
            await app.bot.send_message(
                chat_id=int(family_chat_id),
                text=f"📋 *{name}* — daily summary ({date.today().isoformat()})\n"
                f"✅ Taken: {taken} · ❌ Skipped: {skipped} · ⚠️ Missed: {missed}\n"
                f"🔥 Streak: {streak} days",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as exc:
            logger.warning("guardian daily forward failed for %s: %s", family_chat_id, exc)
