"""OpenRouter async LLM wrapper — OpenAI-compatible, multi-model gateway."""

from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger(__name__)

# Tried in order; first success wins. openrouter/free auto-routes to whatever
# provider is available, making it the most resilient primary choice.
_FALLBACK_MODELS = [
    "openrouter/free",
    "liquid/lfm-2.5-1.2b-instruct:free",
    "openai/gpt-oss-20b:free",
]


async def openrouter_chat(
    *,
    system: str,
    user: str,
    max_tokens: int = 512,
    temperature: float = 0.2,
) -> str:
    """Call OpenRouter chat completions with automatic model fallback."""
    key = settings.openrouter_api_key
    if not key or key.startswith("change-me"):
        raise ValueError("OPENROUTER_API_KEY not configured")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://saath.health",
        "X-Title": "Saath Health Companion",
    }

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
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )

            if resp.status_code == 200:
                data = resp.json()
                text = str(data["choices"][0]["message"]["content"]).strip()
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
