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
    user: str | None = None,
    history: list[dict[str, str]] | None = None,
    max_tokens: int = 512,
    temperature: float = 0.2,
    retries: int = 3,
) -> str:
    """Call NVIDIA NIM chat completions. If `history` is provided, it is
    interleaved between the system prompt and the current `user` turn.
    """
    key = settings.nvidia_api_key
    if not key or key.startswith("change-me"):
        raise ValueError("NVIDIA_API_KEY not configured")

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    if user is not None:
        messages.append({"role": "user", "content": user})

    payload = {
        "model": settings.nvidia_model,
        "messages": messages,
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
            choices = data.get("choices") or []
            if not choices:
                raise RuntimeError("nvidia returned empty choices")
            content = (choices[0].get("message") or {}).get("content") or ""
            text = str(content).strip()
            if not text:
                raise RuntimeError("nvidia returned empty content")
            return text

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
