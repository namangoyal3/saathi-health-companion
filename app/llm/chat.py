"""Unified chat LLM entry point for bot/voice/lab flows.

Provider order:
  1. NVIDIA NIM (nemotron-super-49b, ~0.7s p50) — primary
  2. OpenRouter free tier — fallback when NVIDIA times out or errors

Haiku/Opus are reserved for structured-output paths (DDI, lab vision) and are
NOT used here to keep voice-turn latency low and cost predictable.
"""

from __future__ import annotations

import logging

from app.config import settings
from app.llm.nvidia import nvidia_chat
from app.llm.openrouter import openrouter_chat

log = logging.getLogger(__name__)


async def llm_chat(
    *,
    system: str,
    user: str | None = None,
    history: list[dict[str, str]] | None = None,
    max_tokens: int = 160,
    temperature: float = 0.2,
) -> str:
    """Try NVIDIA first, fall back to OpenRouter. Raises if both fail."""
    # NVIDIA path
    if settings.nvidia_api_key and not settings.nvidia_api_key.startswith("change-me"):
        try:
            return await nvidia_chat(
                system=system,
                user=user,
                history=history,
                max_tokens=max_tokens,
                temperature=temperature,
                retries=2,
            )
        except Exception as exc:
            log.warning("llm_chat nvidia_failed err=%s — falling back to openrouter", exc)

    # OpenRouter fallback
    return await openrouter_chat(
        system=system,
        user=user,
        history=history,
        max_tokens=max_tokens,
        temperature=temperature,
    )
