"""Telegram → Lab PDF ingestion.

When the senior sends a PDF document, we:
  1. Download it to a temp file
  2. Run the Opus vision pipeline (app.labs.vision.parse_lab_pdf)
  3. Ask the LLM for a plain-language narrative
  4. Reply to the sender, and forward to the guardian if linked
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.bot import db
from app.labs.vision import BiomarkerRow, parse_lab_pdf
from app.llm.chat import llm_chat

log = logging.getLogger(__name__)

_NARRATIVE_SYSTEM = """You are Saath, a warm companion explaining lab results in plain language.

Given a list of biomarkers (name, value, unit, flag, ref range), produce a friendly 2-3 sentence summary for a senior.

RULES:
- Plain conversational tone. No bullets, no markdown, no emojis.
- NEVER diagnose. Say "please discuss with your doctor" for any interpretation.
- Use the reference ranges to say what is normal / flagged.
- If everything is normal, say so simply and warmly.
- Respond in the same language the user writes in (English or Hindi)."""


def _biomarkers_to_prompt(rows: list[BiomarkerRow]) -> str:
    lines = []
    for r in rows[:30]:
        ref = ""
        if r.ref_low is not None and r.ref_high is not None:
            ref = f" (normal {r.ref_low}-{r.ref_high})"
        lines.append(f"{r.biomarker}: {r.value} {r.unit} [{r.flag}]{ref}")
    return "\n".join(lines)


async def handle_lab_document(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle PDF uploads — assume they are lab reports for now."""
    if not update.message or not update.message.document:
        return
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    doc = update.message.document
    if doc.mime_type != "application/pdf":
        return

    profile = await db.get_profile(chat_id)
    lang = str((profile or {}).get("language") or "en")

    ack = (
        "Got it — reading your lab report. This takes about 20 seconds…"
        if lang != "hi"
        else "मिल गया — आपकी रिपोर्ट पढ़ रही हूँ। 20 सेकंड लगेंगे…"
    )
    await update.message.reply_text(ack)

    try:
        tg_file = await context.bot.get_file(doc.file_id)
    except Exception as exc:
        log.warning("lab_pdf_fetch_failed err=%s", exc)
        await update.message.reply_text(
            "Sorry, couldn't download the file. Please try again."
        )
        return

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        await tg_file.download_to_drive(custom_path=str(tmp_path))

        try:
            rows = await asyncio.to_thread(parse_lab_pdf, tmp_path)
        except Exception as exc:
            log.error("lab_pdf_parse_failed err=%s", exc)
            await update.message.reply_text(
                "I had trouble reading this lab report. Please try a clearer scan."
            )
            return

        if not rows:
            await update.message.reply_text(
                "I couldn't extract any readings from that PDF. "
                "If the scan is blurry, please share a clearer copy."
            )
            return

        prompt = _biomarkers_to_prompt(rows)
        try:
            narrative = await llm_chat(
                system=_NARRATIVE_SYSTEM, user=prompt, max_tokens=180
            )
        except Exception as exc:
            log.error("lab_narrative_failed err=%s", exc)
            flagged = [r for r in rows if r.flag in ("low", "high")]
            if flagged:
                narrative = (
                    f"I found {len(rows)} readings. {len(flagged)} are outside the normal range. "
                    "Please discuss these with your doctor."
                )
            else:
                narrative = (
                    f"I found {len(rows)} readings and all of them look normal. "
                    "Please still share this with your doctor at your next visit."
                )

        header = f"📋 Lab report ({len(rows)} readings)"
        await update.message.reply_text(
            f"*{header}*\n\n{narrative}", parse_mode=ParseMode.MARKDOWN
        )

        family_chat_id = (profile or {}).get("family_chat_id")
        if family_chat_id:
            name = str((profile or {}).get("name") or "your loved one")
            flagged = [r for r in rows if r.flag in ("low", "high")]
            flagged_lines = (
                "\n".join(
                    f"• {r.biomarker}: {r.value} {r.unit} ({r.flag})"
                    for r in flagged[:10]
                )
                or "All biomarkers within normal range."
            )
            try:
                await context.bot.send_message(
                    chat_id=int(family_chat_id),
                    text=(
                        f"📋 *Lab report shared by {name}*\n\n"
                        f"{narrative}\n\n"
                        f"_Key readings:_\n{flagged_lines}"
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception as exc:
                log.warning("lab_forward_guardian_failed err=%s", exc)
    finally:
        import contextlib
        with contextlib.suppress(Exception):
            tmp_path.unlink()
