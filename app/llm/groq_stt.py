"""Groq Whisper wrapper — free, fast audio → text for Telegram voice messages."""

from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)


async def transcribe(audio_bytes: bytes, filename: str = "voice.ogg") -> str | None:
    """Transcribe OGG/OPUS (or any ffmpeg-readable) audio to text.

    Returns the transcription, or None if Groq is not configured or fails.
    The senior's Telegram voice note arrives as OGG/OPUS — Whisper handles it natively.
    """
    key = settings.groq_api_key
    if not key or key.startswith("change-me"):
        return None

    headers = {"Authorization": f"Bearer {key}"}
    files = {"file": (filename, audio_bytes, "audio/ogg")}
    data = {"model": settings.groq_whisper_model, "response_format": "json"}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.groq_base_url}/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
            )
        if resp.status_code == 200:
            return str(resp.json().get("text", "")).strip() or None
        log.warning("groq_whisper_status=%d body=%s", resp.status_code, resp.text[:200])
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        log.warning("groq_whisper_network_err=%s", exc)
    return None
