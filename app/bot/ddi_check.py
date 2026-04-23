"""DDI check triggered after onboarding confirmation.

Reads the senior's current medication list, runs DDISubAgent (Opus 4.7 xhigh),
and — if HIGH or MEDIUM flags exist — sends a plain-language summary to the
senior and, if linked, to the guardian.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from telegram import Bot
from telegram.constants import ParseMode
from telegram.ext import Application

from app.agents.ddi import DDIFlag, DDIInput, MedicationInput
from app.agents.ddi import run as run_ddi_agent
from app.bot import db
from app.config import settings

log = logging.getLogger(__name__)


def _dose_to_mg(dose: str | None) -> Decimal:
    """Best-effort: "500mg" → 500, "5 mg" → 5, anything unreadable → 0."""
    if not dose:
        return Decimal(0)
    import re

    m = re.search(r"(\d+(?:\.\d+)?)", dose)
    return Decimal(m.group(1)) if m else Decimal(0)


def _summarise(flags: list[DDIFlag]) -> str:
    high = [f for f in flags if f.severity == "HIGH"]
    medium = [f for f in flags if f.severity == "MEDIUM"]
    if not high and not medium:
        return ""
    lines: list[str] = []
    for f in high + medium:
        drugs = " + ".join(f.drugs_involved)
        lines.append(f"• *{f.severity}* ({drugs}): {f.finding}")
    header = "⚠️ *Medication interaction check*"
    footer = "_Informational summary only — physician review recommended before any dose change._"
    return f"{header}\n\n" + "\n".join(lines) + f"\n\n{footer}"


async def run_ddi_for_profile(chat_id: int, application: Application) -> None:
    """Fetch current meds → run DDI agent → send summary to senior + guardian if flags exist."""
    if not settings.anthropic_api_key or settings.anthropic_api_key.startswith("change-me"):
        log.info("ddi_check_skipped reason=no_anthropic_key chat=%s", chat_id)
        return

    profile = await db.get_profile(chat_id)
    if not profile:
        return

    meds = await db.get_medications(chat_id)
    if len(meds) < 2:
        # No interaction possible with zero or one medication
        return

    ddi_input = DDIInput(
        senior_id=uuid.uuid4(),  # ephemeral — bot chat_id not tied to app_user.id
        medications=[
            MedicationInput(
                name=str(m["drug_name"]),
                dose_mg=_dose_to_mg(m.get("dose")),
                frequency_rrule=f"FREQ=DAILY;COUNT={len(m.get('timings') or [])}",
                start_date=datetime.now(UTC).date().isoformat(),
            )
            for m in meds
        ],
        recent_labs=[],
        recent_symptoms=[],
    )

    try:
        result = await run_ddi_agent(ddi_input)
    except Exception as exc:
        log.warning("ddi_check_failed chat=%s err=%s", chat_id, exc)
        return

    summary = _summarise(result.flags)
    if not summary:
        return  # no noteworthy interactions

    bot = Bot(token=settings.telegram_bot_token) if settings.telegram_bot_token else None
    application_bot = application.bot if bot is None else bot

    try:
        await application_bot.send_message(
            chat_id=chat_id, text=summary, parse_mode=ParseMode.MARKDOWN
        )
    except Exception as exc:
        log.warning("ddi_send_to_senior_failed chat=%s err=%s", chat_id, exc)

    family_chat_id = profile.get("family_chat_id")
    if family_chat_id:
        name = str(profile.get("name") or "your loved one")
        try:
            await application_bot.send_message(
                chat_id=int(family_chat_id),
                text=f"⚠️ *Interaction flag for {name}*\n\n{summary}",
                parse_mode=ParseMode.MARKDOWN,
            )
        except Exception as exc:
            log.warning("ddi_send_to_guardian_failed chat=%s err=%s", family_chat_id, exc)
