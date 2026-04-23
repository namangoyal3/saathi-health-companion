"""NVIDIA NIM async LLM wrapper — OpenAI-compatible endpoint, free-tier models.

Default: nvidia/llama-3.1-nemotron-70b-instruct
Override via NVIDIA_MODEL in .env.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)

_HEADERS = {
    "Content-Type": "application/json",
}


async def nvidia_chat(
    *,
    system: str,
    user: str,
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> str:
    """Call NVIDIA NIM chat completions. Returns the assistant message text."""
    key = settings.nvidia_api_key
    if not key or key.startswith("change-me"):
        raise ValueError("NVIDIA_API_KEY not configured")

    payload = {
        "model": settings.nvidia_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.nvidia_base_url}/chat/completions",
            headers={**_HEADERS, "Authorization": f"Bearer {key}"},
            json=payload,
        )

    if resp.status_code != 200:
        log.error("nvidia_nim_error status=%d body=%s", resp.status_code, resp.text[:200])
        resp.raise_for_status()

    data = resp.json()
    return str(data["choices"][0]["message"]["content"])
