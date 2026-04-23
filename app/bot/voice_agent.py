"""AI voice agent for Telegram — NVIDIA Nemotron (+ OpenRouter fallback) + ElevenLabs + Groq STT + memory."""

from __future__ import annotations

import asyncio
import io
import logging
import re

import asyncpg
import httpx
from telegram import Update
from telegram.ext import ContextTypes

from app.bot import db
from app.config import settings
from app.llm.chat import llm_chat
from app.llm.emergency import emergency_reply, is_emergency
from app.llm.groq_stt import transcribe

# Strong refs to background tasks so the event loop doesn't GC them mid-flight.
_background_tasks: set[asyncio.Task[None]] = set()


def _spawn_background(coro: asyncio.Future[None] | object) -> None:
    task = asyncio.create_task(coro)  # type: ignore[arg-type]
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


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
            "ffmpeg",
            "-i",
            "pipe:0",
            "-c:a",
            "libopus",
            "-b:a",
            "24k",
            "-vbr",
            "on",
            "-f",
            "ogg",
            "pipe:1",
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


async def _recent_vitals_context(chat_id: int) -> str:
    """Fetch the last 3 vitals anomalies for this chat_id's linked senior.

    Returns empty string when no senior is linked or no anomalies exist.
    Joins bot_profile.chat_id → app_user.telegram_chat_id to resolve the
    senior UUID, then reads vitals_anomaly.
    """
    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
        )
    except Exception as exc:
        log.debug("vitals_context_db_connect_failed err=%s", exc)
        return ""
    try:
        rows = await conn.fetch(
            """SELECT va.marker, va.severity, va.value, va.threshold,
                      va.narrative, va.summary_date
               FROM vitals_anomaly va
               JOIN app_user u ON u.id = va.senior_id
               WHERE u.telegram_chat_id = $1
               ORDER BY va.created_at DESC
               LIMIT 3""",
            str(chat_id),
        )
    except Exception as exc:
        log.debug("vitals_context_query_failed err=%s", exc)
        return ""
    finally:
        await conn.close()

    if not rows:
        return ""

    lines = [f"- {r['summary_date']} · {r['severity']} · {r['narrative']}" for r in rows]
    return "RECENT SMARTWATCH FLAGS (last 3, most recent first):\n" + "\n".join(lines)


async def _build_system(chat_id: int) -> str:
    """Compose the system prompt with profile + meds + recent vitals flags."""
    system = _SYSTEM
    profile = await db.get_profile(chat_id)
    if not profile:
        return system

    name = profile.get("name", "")
    conditions = ", ".join(str(c) for c in (profile.get("conditions") or []))
    meds = await db.get_medications(chat_id)
    med_list = (
        ", ".join(f"{m['drug_name']} {m.get('dose') or ''}".strip() for m in meds)
        if meds
        else "not specified"
    )
    vitals_block = await _recent_vitals_context(chat_id)

    header = (
        f"You are Saath, a warm AI health companion.\n"
        f"You are speaking with {name}.\n"
        f"Their conditions: {conditions or 'not specified'}.\n"
        f"Their medications: {med_list}.\n"
    )
    if vitals_block:
        header += (
            f"\n{vitals_block}\n"
            "If the user mentions how they feel, acknowledge these recent flags naturally "
            "without alarming them; stay within the STRICT OUTPUT RULES below.\n"
        )
    header += "\n"

    return header + _SYSTEM[_SYSTEM.index("STRICT OUTPUT RULES") :]


async def _generate_reply(chat_id: int, user_text: str) -> str:
    """LLM call with conversational memory. Memory is appended after the reply lands."""
    system = await _build_system(chat_id)
    history = await db.get_conv(chat_id, limit=10)
    try:
        reply = await llm_chat(system=system, user=user_text, history=history, max_tokens=160)
    except Exception as exc:
        log.error("ai_message_llm_failed err=%s", exc)
        reply = "I'm having a little trouble right now. Please try again in a moment."
    reply = _strip_markdown(reply)

    try:
        await db.append_conv(chat_id, "user", user_text)
        await db.append_conv(chat_id, "assistant", reply)
    except Exception as exc:
        log.warning("conv_memory_persist_failed err=%s", exc)
    return reply


async def _send_voice_async(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action="record_voice")
        ogg = await _fetch_voice(text)
        if ogg:
            await context.bot.send_voice(chat_id=chat_id, voice=io.BytesIO(ogg))
    except Exception as exc:
        log.warning("send_voice_failed err=%s", exc)


async def handle_ai_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any text message with LLM response + ElevenLabs voice note."""
    if not update.message:
        return

    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    # Deterministic emergency guard — short-circuit BEFORE calling the LLM.
    # Free-tier models drift off the prompt's emergency rule; regex never does.
    if is_emergency(user_text):
        log.warning("bot_emergency_triggered chat_id=%s text=%r", chat_id, user_text[:120])
        profile = await db.get_profile(chat_id)
        lang = str((profile or {}).get("language") or "en")
        reply = emergency_reply(lang)
        await update.message.reply_text(reply)
        _spawn_background(_send_voice_async(context, chat_id, reply))
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    reply = await _generate_reply(chat_id, user_text)

    # Send text immediately, then voice note asynchronously
    await update.message.reply_text(reply)
    _spawn_background(_send_voice_async(context, chat_id, reply))


async def _download_voice(context: ContextTypes.DEFAULT_TYPE, file_id: str) -> bytes | None:
    try:
        tg_file = await context.bot.get_file(file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(out=buf)
        return buf.getvalue()
    except Exception as exc:
        log.warning("voice_download_failed err=%s", exc)
        return None


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """User sent a voice note — transcribe via Groq Whisper, then run the AI turn."""
    if not update.message:
        return
    chat_id = update.effective_chat.id  # type: ignore[union-attr]
    voice = update.message.voice or update.message.audio
    if voice is None:
        return

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    audio = await _download_voice(context, voice.file_id)
    if audio is None:
        await update.message.reply_text(
            "Sorry, I couldn't fetch your voice message. Please try again."
        )
        return

    transcript = await transcribe(audio, filename="voice.ogg")
    if not transcript:
        profile = await db.get_profile(chat_id)
        lang = str((profile or {}).get("language") or "en")
        msg = (
            "I couldn't hear that clearly — please type your message."
            if lang != "hi"
            else "मैं आपकी आवाज़ साफ़ नहीं सुन पाई — कृपया टाइप करें।"
        )
        await update.message.reply_text(msg)
        return

    # Quote-reply with the transcription so the user knows what we heard
    await update.message.reply_text(f"🎙 _{transcript}_", parse_mode="Markdown")

    # Emergency guard on the transcribed text — same safety net as text input
    if is_emergency(transcript):
        log.warning("bot_voice_emergency_triggered chat_id=%s text=%r", chat_id, transcript[:120])
        profile = await db.get_profile(chat_id)
        lang = str((profile or {}).get("language") or "en")
        reply = emergency_reply(lang)
        await update.message.reply_text(reply)
        _spawn_background(_send_voice_async(context, chat_id, reply))
        return

    reply = await _generate_reply(chat_id, transcript)
    await update.message.reply_text(reply)
    _spawn_background(_send_voice_async(context, chat_id, reply))
