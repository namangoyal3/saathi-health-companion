"""AI voice agent for Telegram — OpenRouter LLM + ElevenLabs voice note."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import subprocess

import httpx
from telegram import Update
from telegram.ext import ContextTypes

from app.bot import db
from app.config import settings
from app.llm.openrouter import openrouter_chat

log = logging.getLogger(__name__)

_SYSTEM = """You are Saath, a warm and caring AI health companion for aging Indian parents.

You are assisting a senior citizen. Speak warmly and simply, like a trusted companion.

STRICT OUTPUT RULES:
- Write ONLY plain conversational sentences. NO bullet points, NO lists, NO dashes.
- NO markdown: no bold (**), no italics (*), no headers (#).
- NO emojis whatsoever.
- Maximum 2-3 short sentences. This is read aloud — keep it brief.
- Never diagnose or prescribe. Say "please discuss with your doctor" for clinical decisions.
- If user reports chest pain, breathlessness, stroke symptoms, fainting, or severe injury — say exactly: "Please call emergency services at 112 immediately." and nothing else.
- Respond in the same language the user writes in (English or Hindi)."""


def _strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{2,}", " ", text)
    text = re.sub(r"\n", " ", text)
    return text.strip()


async def _mp3_to_ogg(mp3_bytes: bytes) -> bytes | None:
    """Convert MP3 bytes to OGG/OPUS using ffmpeg (required for Telegram voice notes)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", "pipe:0",
            "-c:a", "libopus", "-b:a", "24k",
            "-vbr", "on", "-f", "ogg", "pipe:1",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(mp3_bytes), timeout=15)
        if proc.returncode == 0 and stdout:
            return stdout
    except Exception as exc:
        log.warning("mp3_to_ogg_failed err=%s", exc)
    return None


async def _fetch_voice(text: str) -> bytes | None:
    """Fetch ElevenLabs MP3 and convert to OGG for Telegram."""
    key = settings.elevenlabs_api_key
    if not key or key.startswith("change-me"):
        return None
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{settings.elevenlabs_voice_id}",
                headers={"xi-api-key": key},
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                },
            )
        if resp.status_code == 200:
            return await _mp3_to_ogg(resp.content)
        log.warning("elevenlabs_error status=%d", resp.status_code)
    except Exception as exc:
        log.warning("fetch_voice_failed err=%s", exc)
    return None


async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any text message with LLM response + ElevenLabs voice note."""
    if not update.message:
        return

    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Build a personalised system prompt if the user has a profile
    system = _SYSTEM
    profile = await db.get_profile(chat_id)
    if profile:
        name = profile.get("name", "")
        conditions = ", ".join(str(c) for c in (profile.get("conditions") or []))
        meds = await db.get_medications(chat_id)
        med_list = ", ".join(
            f"{m['drug_name']} {m.get('dose') or ''}".strip() for m in meds
        ) if meds else "not specified"
        system = (
            f"You are Saath, a warm AI health companion.\n"
            f"You are speaking with {name}.\n"
            f"Their conditions: {conditions or 'not specified'}.\n"
            f"Their medications: {med_list}.\n\n"
        ) + _SYSTEM[_SYSTEM.index("STRICT OUTPUT RULES"):]

    try:
        reply = await openrouter_chat(system=system, user=user_text, max_tokens=120)
        reply = _strip_markdown(reply)
    except Exception as exc:
        log.error("ai_message_llm_failed err=%s", exc)
        reply = "I'm having a little trouble right now. Please try again in a moment."

    # Send text immediately
    await update.message.reply_text(reply)

    # Send voice note asynchronously so text isn't delayed
    async def _send_voice() -> None:
        try:
            await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
            ogg = await _fetch_voice(reply)
            if ogg:
                await context.bot.send_voice(
                    chat_id=chat_id,
                    voice=io.BytesIO(ogg),
                )
        except Exception as exc:
            log.warning("send_voice_failed err=%s", exc)

    asyncio.create_task(_send_voice())


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User sent a voice message — ask them to type for now."""
    if not update.message:
        return
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    profile = await db.get_profile(chat_id)
    lang = str((profile or {}).get("language") or "en")
    msg = (
        "Please type your message — I can read Hindi or English."
        if lang != "hi"
        else "कृपया अपना संदेश टाइप करें — मैं हिंदी और अंग्रेजी पढ़ सकती हूं।"
    )
    await update.message.reply_text(msg)
