"""OpenRouter async LLM wrapper — OpenAI-compatible, multi-model gateway."""

from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)


async def openrouter_chat(
    *,
    system: str,
    user: str,
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> str:
    """Call OpenRouter chat completions. Returns the assistant message text."""
    key = settings.openrouter_api_key
    if not key or key.startswith("change-me"):
        raise ValueError("OPENROUTER_API_KEY not configured")

    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://saath.health",
                "X-Title": "Saath Health Companion",
            },
            json=payload,
        )

    if resp.status_code != 200:
        log.error("openrouter_error status=%d body=%s", resp.status_code, resp.text[:200])
        resp.raise_for_status()

    data = resp.json()
    return str(data["choices"][0]["message"]["content"])
