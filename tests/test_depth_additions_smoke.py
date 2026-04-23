"""End-to-end smoke test for depth-addition flows.

Covers (in order of demo impact):
  1. Conversational memory: append → retrieve → prune semantics
  2. Guardian link code: create → consume → family_chat_id set
  3. Adherence streak: reads bot_med_event + active meds
  4. Bot registration surfaces: ensure all handlers are registered

Does NOT exercise: ElevenLabs, Groq, OpenRouter (those are integration-tier).
"""

from __future__ import annotations

import pytest

from app.bot import db as bot_db


@pytest.mark.asyncio
async def test_conv_memory_append_and_retrieve() -> None:
    await bot_db.init_pool()
    chat_id = 999_001
    try:
        await bot_db.clear_conv(chat_id)

        # Empty history returns empty list
        assert await bot_db.get_conv(chat_id) == []

        # Append turns in order
        await bot_db.append_conv(chat_id, "user", "I have knee pain")
        await bot_db.append_conv(chat_id, "assistant", "I'm sorry to hear that")
        await bot_db.append_conv(chat_id, "user", "It hurts when I walk")

        hist = await bot_db.get_conv(chat_id, limit=10)
        assert len(hist) == 3
        assert hist[0]["role"] == "user"
        assert hist[0]["content"] == "I have knee pain"
        assert hist[-1]["content"] == "It hurts when I walk"
    finally:
        await bot_db.clear_conv(chat_id)
        await bot_db.close_pool()


@pytest.mark.asyncio
async def test_conv_memory_prunes_to_keep_limit() -> None:
    await bot_db.init_pool()
    chat_id = 999_002
    try:
        await bot_db.clear_conv(chat_id)
        for i in range(15):
            await bot_db.append_conv(chat_id, "user", f"msg {i}", keep=5)

        hist = await bot_db.get_conv(chat_id, limit=10)
        assert len(hist) == 5
        # Last 5 should be msg 10..14 (we kept the newest)
        assert hist[-1]["content"] == "msg 14"
    finally:
        await bot_db.clear_conv(chat_id)
        await bot_db.close_pool()


@pytest.mark.asyncio
async def test_guardian_link_code_lifecycle() -> None:
    await bot_db.init_pool()
    senior_chat_id = 999_101
    guardian_chat_id = 999_102
    try:
        # Create profile for the senior so set_family_chat_id finds a row
        await bot_db.save_profile(senior_chat_id, "Lakshmi Iyer", "en", ["diabetes"])

        await bot_db.create_link_code(senior_chat_id, "TEST01")

        resolved = await bot_db.consume_link_code("TEST01")
        assert resolved == senior_chat_id

        # Second consumption of the same code returns None (already consumed)
        assert await bot_db.consume_link_code("TEST01") is None

        await bot_db.set_family_chat_id(senior_chat_id, guardian_chat_id)

        profile = await bot_db.get_profile(senior_chat_id)
        assert profile is not None
        assert profile["family_chat_id"] == guardian_chat_id

        seniors = await bot_db.get_seniors_for_guardian(guardian_chat_id)
        assert any(s["chat_id"] == senior_chat_id for s in seniors)
    finally:
        await bot_db.delete_profile(senior_chat_id)
        await bot_db.close_pool()


@pytest.mark.asyncio
async def test_invalid_link_code_returns_none() -> None:
    await bot_db.init_pool()
    try:
        assert await bot_db.consume_link_code("NOPE99") is None
    finally:
        await bot_db.close_pool()


@pytest.mark.asyncio
async def test_adherence_streak_zero_with_no_meds() -> None:
    await bot_db.init_pool()
    chat_id = 999_201
    try:
        await bot_db.save_profile(chat_id, "Test", "en", [])
        # No medications → streak is 0
        assert await bot_db.get_adherence_streak(chat_id) == 0
    finally:
        await bot_db.delete_profile(chat_id)
        await bot_db.close_pool()


@pytest.mark.asyncio
async def test_bot_application_registers_all_handlers() -> None:
    """Smoke: import chain works + all new commands are registered."""
    import os

    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake-token-for-smoke")

    from app.bot.application import build_application

    app = build_application("fake-token-for-smoke")
    # Collect all CommandHandlers registered
    commands: set[str] = set()
    for group_list in app.handlers.values():
        for h in group_list:
            if hasattr(h, "commands") and h.commands:
                commands.update(h.commands)

    # Depth-addition commands must be registered at the top level
    assert "link_guardian" in commands
    assert "link_senior" in commands
    assert "report" in commands
    # /status is a top-level command; /start lives inside the ConversationHandler
    assert "status" in commands

    # Verify ConversationHandler carries /start as an entry point
    from telegram.ext import ConversationHandler

    conv_starts: set[str] = set()
    for group_list in app.handlers.values():
        for h in group_list:
            if isinstance(h, ConversationHandler):
                for entry in h.entry_points:
                    if hasattr(entry, "commands") and entry.commands:
                        conv_starts.update(entry.commands)
    assert "start" in conv_starts


@pytest.mark.asyncio
async def test_ddi_check_skips_when_no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """DDI check should be a no-op if Anthropic key is not configured."""
    from app.bot.ddi_check import run_ddi_for_profile

    await bot_db.init_pool()
    chat_id = 999_301
    try:
        # Blank API key → early return, no exception
        from app.config import settings as cfg

        monkeypatch.setattr(cfg, "anthropic_api_key", "")

        await bot_db.save_profile(chat_id, "Test", "en", [])

        # Application is not needed for the early-return path — pass None-like
        class _DummyApp:
            class _Bot:
                async def send_message(self, **_: object) -> None:
                    return None

            bot = _Bot()

        await run_ddi_for_profile(chat_id, _DummyApp())  # type: ignore[arg-type]
        # If we got here without exception, the skip path works
    finally:
        await bot_db.delete_profile(chat_id)
        await bot_db.close_pool()
