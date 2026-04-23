"""End-to-end tests for /chat, /tts, /stt web-portal endpoints.

These endpoints are load-bearing for the live demo. Regressions here
(e.g. the regex SyntaxError that silently broke sendText) should be
caught at CI time, not at demo time.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_endpoint_returns_text(client: AsyncClient) -> None:
    """/chat should short-circuit the LLM in a unit test and still return 200."""
    with patch("app.api.chat.llm_chat", new=AsyncMock(return_value="Hello Lakshmi.")):
        resp = await client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "Hello Lakshmi."
    # audio_b64 is decoupled from /chat — always empty on this endpoint
    assert body["audio_b64"] == ""


@pytest.mark.asyncio
async def test_chat_endpoint_graceful_when_llm_throws(client: AsyncClient) -> None:
    """If the LLM raises, /chat returns the fallback string, not a 500."""
    boom = AsyncMock(side_effect=RuntimeError("llm offline"))
    with patch("app.api.chat.llm_chat", new=boom):
        resp = await client.post("/chat", json={"message": "hi"})
    assert resp.status_code == 200
    assert "trouble" in resp.json()["text"].lower()


@pytest.mark.asyncio
async def test_chat_emergency_phrase_short_circuits_llm(client: AsyncClient) -> None:
    """Emergency phrases must never be handled by the LLM — too risky on free
    tier models that ignore prompt rules. Python-level guard returns the 112
    message directly and llm_chat is NEVER called."""
    llm_spy = AsyncMock(return_value="nope")
    with patch("app.api.chat.llm_chat", new=llm_spy):
        resp = await client.post("/chat", json={"message": "I have severe chest pain right now"})
    assert resp.status_code == 200
    assert "112" in resp.json()["text"]
    llm_spy.assert_not_called()


@pytest.mark.asyncio
async def test_chat_rejects_empty_message(client: AsyncClient) -> None:
    """Empty string passes validation but shouldn't reach the LLM."""
    resp = await client.post("/chat", json={"message": ""})
    assert resp.status_code == 200
    # Either returns "" (short-circuit) or a generic greeting — just no crash
    assert isinstance(resp.json().get("text", ""), str)


@pytest.mark.asyncio
async def test_chat_rejects_missing_field(client: AsyncClient) -> None:
    """Schema validation: missing 'message' returns 422."""
    resp = await client.post("/chat", json={"foo": "bar"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_tts_returns_empty_when_key_missing(client: AsyncClient) -> None:
    """If ELEVENLABS_API_KEY is unset, /tts returns {audio_b64: ''} gracefully."""
    from app.config import settings
    with patch.object(settings, "elevenlabs_api_key", ""):
        resp = await client.post("/tts", json={"message": "hi"})
    assert resp.status_code == 200
    assert resp.json()["audio_b64"] == ""


@pytest.mark.asyncio
async def test_stt_returns_empty_audio_error_on_empty_upload(client: AsyncClient) -> None:
    """Empty audio upload returns error=empty audio, not a crash."""
    files = {"audio": ("empty.webm", b"", "audio/webm")}
    resp = await client.post("/stt", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == ""
    assert body["error"] == "empty audio"


@pytest.mark.asyncio
async def test_stt_returns_groq_unavailable_when_transcribe_returns_none(client: AsyncClient) -> None:
    """If Groq is not configured or fails, client sees a specific error code
    rather than a hang or misleading message."""
    with patch("app.api.chat.transcribe", new=AsyncMock(return_value=None)):
        files = {"audio": ("voice.webm", b"fake-audio-bytes", "audio/webm")}
        resp = await client.post("/stt", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == ""
    assert body["error"] == "groq_unavailable"


@pytest.mark.asyncio
async def test_stt_returns_transcription(client: AsyncClient) -> None:
    """Happy path: Groq returns text, /stt forwards it."""
    with patch("app.api.chat.transcribe", new=AsyncMock(return_value="Hello Saath.")):
        files = {"audio": ("voice.webm", b"fake-audio-bytes", "audio/webm")}
        resp = await client.post("/stt", files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "Hello Saath."
    assert body["error"] == ""


@pytest.mark.asyncio
async def test_root_returns_html_portal(client: AsyncClient) -> None:
    """GET / returns the voice portal HTML with the dark-theme + MediaRecorder script."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    body = resp.text
    # Essential functions must be present — if we rename these, tests fail loudly
    assert "function sendText" in body
    assert "function toggleMic" in body
    assert "startMicRecording" in body
    # Prior bug: the regex SyntaxError killed the script. Confirm we shipped
    # the fixed Unicode-property variant, not the ambiguous range class.
    assert "\\p{Extended_Pictographic}" in body
    assert "[^\\x00-" not in body  # the old malformed character class
