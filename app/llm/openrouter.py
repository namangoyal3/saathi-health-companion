"""OpenRouter async LLM wrapper — OpenAI-compatible, multi-model gateway."""

from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# Tried in order; first success wins.
# NOTE: "openrouter/free" is NOT a valid model id on OpenRouter — it was
# returning HTTP 400 for every request. Removed per discovery in
# auraCodesKM/sath_claude commit 8d5d170.
_FALLBACK_MODELS = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "inclusionai/ling-2.6-flash:free",
    "z-ai/glm-4.5-air:free",
    "openai/gpt-oss-120b:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "liquid/lfm-2.5-1.2b-instruct:free",
]


async def openrouter_chat(
    *,
    system: str,
    user: str | None = None,
    history: list[dict[str, str]] | None = None,
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> str:
    """Call OpenRouter chat completions with automatic model fallback.

    If `history` is provided, it is interleaved between the system prompt and the
    current `user` turn. Each history entry is `{"role": "user|assistant", "content": "..."}`.
    """
    key = settings.openrouter_api_key
    if not key or key.startswith("change-me"):
        raise ValueError("OPENROUTER_API_KEY not configured")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://saath.health",
        "X-Title": "Saath Health Companion",
    }

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    if user is not None:
        messages.append({"role": "user", "content": user})

    models = [settings.openrouter_model] + [
        m for m in _FALLBACK_MODELS if m != settings.openrouter_model
    ]

    last_err: Exception = RuntimeError("no models tried")
    for model in models:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    f"{settings.openrouter_base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )

            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    log.warning("openrouter_empty_choices model=%s", model)
                    last_err = RuntimeError(f"empty choices from {model}")
                    continue
                content = (choices[0].get("message") or {}).get("content") or ""
                text = str(content).strip()
                if text:
                    if model != settings.openrouter_model:
                        log.info("openrouter_fallback used=%s", model)
                    return text

            log.warning("openrouter_skip model=%s status=%d", model, resp.status_code)
            last_err = httpx.HTTPStatusError(
                f"HTTP {resp.status_code}", request=resp.request, response=resp
            )

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            log.warning("openrouter_timeout model=%s err=%s", model, exc)
            last_err = exc

    raise last_err
