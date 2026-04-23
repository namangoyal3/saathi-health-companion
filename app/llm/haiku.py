"""Haiku 4.5 call wrapper — latency-critical hot path (≤200 ms TTFT target)."""

from __future__ import annotations

import uuid
from typing import Any, cast

import anthropic

from app.config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def haiku_call(
    *,
    system: str,
    user: str,
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 1024,
    senior_id: uuid.UUID | None = None,
    agent_name: str = "haiku",
) -> anthropic.types.Message:
    """Call Haiku 4.5 — no thinking, no memory tool.

    Never block a user-facing voice turn on Opus. This wrapper is for all
    latency-critical paths: IVR scripts, intent classification, safety gatekeeper,
    response shorteners.
    """
    return cast(
        anthropic.types.Message,
        _client.messages.create(  # type: ignore[call-overload]
            model=settings.model_haiku,
            max_tokens=max_tokens,
            system=system,
            tools=tools or [],
            messages=[{"role": "user", "content": user}],
            metadata={
                "agent": agent_name,
                "senior_id": str(senior_id) if senior_id else "",
            },
        ),
    )
