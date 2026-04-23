"""NVIDIA NIM async LLM wrapper — OpenAI-compatible endpoint, free-tier models.

Default: meta/llama-3.1-8b-instruct
Override via NVIDIA_MODEL in .env.
"""

from __future__ import annotations

import asyncio
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
    retries: int = 3,
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

    last_exc: Exception = RuntimeError("no attempts made")
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
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

        except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.TimeoutException) as exc:
            last_exc = exc
            log.warning("nvidia_timeout attempt=%d/%d", attempt + 1, retries)
            if attempt < retries - 1:
                await asyncio.sleep(1.5 * (attempt + 1))

        except Exception as exc:
            last_exc = exc
            log.error("nvidia_error attempt=%d err=%s", attempt + 1, exc)
            if attempt < retries - 1:
                await asyncio.sleep(1.0)

    raise last_exc
