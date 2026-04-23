"""Opus 4.7 call wrapper — verified adaptive thinking shape (not Tech Spec §5.2).

See docs/docs-verification-2026-04-23.md for the full divergence record.
type:"enabled" with budget_tokens is rejected HTTP 400 on Opus 4.7.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, cast

import anthropic

from app.config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


def opus_call(
    *,
    system: str | list[dict[str, Any]],
    user: str | list[dict[str, Any]],
    effort: Literal["low", "medium", "high", "xhigh", "max"] = "high",
    tools: list[dict[str, Any]] | None = None,
    max_tokens: int = 4096,
    senior_id: uuid.UUID | None = None,
    agent_name: str = "opus",
    display: Literal["omitted", "summarized"] = "summarized",
) -> anthropic.types.Message:
    """Call Opus 4.7 with adaptive thinking.

    Every call includes the memory tool and required metadata for Langfuse tracing.
    The memory tool is path-isolated to MEMORY_ROOT/{senior_id}/ by the adapter.

    display defaults to "summarized" — Opus 4.7 defaults to "omitted" so we must
    set it explicitly whenever we want the thinking trace visible.
    """
    memory_tool: dict[str, Any] = {"type": "memory_20250818", "name": "memory"}
    all_tools: list[dict[str, Any]] = [memory_tool] + (tools or [])

    return cast(
        anthropic.types.Message,
        _client.messages.create(  # type: ignore[call-overload]
            model=settings.model_opus,
            max_tokens=max_tokens,
            thinking={"type": "adaptive", "display": display},
            output_config={"effort": effort},
            system=system,
            tools=all_tools,
            messages=[{"role": "user", "content": user}],
            metadata={
                "agent": agent_name,
                "senior_id": str(senior_id) if senior_id else "",
            },
        ),
    )
