"""SafetyGatekeeper — Haiku 4.5 filter for every user-facing string.

Every guardian-facing output (Telegram, IVR, PDF, dashboard) MUST pass through
check() before delivery. The @safety_gated decorator wraps async functions that
return a string and gates the return value automatically.
"""

from __future__ import annotations

import functools
import json
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

from app.llm.haiku import haiku_call

_SYSTEM_PROMPT = """You are SafetyGatekeeper, a medical language safety filter for Saath, an AI health companion.

Your job: receive a piece of text and return a JSON object determining whether it is safe to deliver to a patient or physician.

EMERGENCY TERMS (return emergency=true, do NOT rewrite, pass text through unchanged):
- chest pain, chest tightness, heart attack
- severe breathlessness, cannot breathe
- stroke symptoms: sudden weakness on one side, facial droop, slurred speech, sudden severe headache
- suicidal ideation, wants to end life
- fainting, loss of consciousness, unresponsive
- acute severe injury, severe bleeding

FORBIDDEN PATTERNS (rewrite or block):
1. Disease diagnosis statements: "you have diabetes", "you have CKD", "you are hypothyroid" → rewrite to objective findings
2. The word "abnormal" describing a test result → rewrite to objective value
3. Dosage instructions: "take 5mg of X", "reduce to 2.5mg" → block entirely (ok=false)
4. Disease probability percentages: "85% chance of..." → rewrite removing the percentage
5. "your screening result", "your test result" → rewrite to neutral phrasing

ALLOWED:
- Objective biomarker values: "eGFR is 58", "HbA1c is 7.2"
- Trend language: "eGFR has declined from 78 to 58 over four quarters"
- Literature references: "associated with Amlodipine + Telmisartan in the literature"
- Action recommendations: "consider discussing with a physician", "physician review recommended"

OUTPUT FORMAT (JSON only, no prose):
{
  "ok": true|false,
  "text": "rewritten or original text",
  "rewritten": true|false,
  "emergency": true|false,
  "reason": "explanation if ok=false or rewritten=true, else null"
}"""


@dataclass
class SafetyResult:
    ok: bool
    text: str
    rewritten: bool
    emergency: bool
    reason: str | None


async def check(
    text: str,
    *,
    context: str = "telegram",
    agent: str = "unknown",
    senior_id: uuid.UUID | None = None,
) -> SafetyResult:
    """Run the safety gatekeeper on a string.

    On LLM failure: default-deny (ok=False) to protect against silent bypass.
    """
    user_payload = json.dumps(
        {"text": text, "context": context, "agent": agent},
        ensure_ascii=False,
    )

    try:
        msg = haiku_call(
            system=_SYSTEM_PROMPT,
            user=user_payload,
            max_tokens=1024,
            senior_id=senior_id,
            agent_name="safety-gatekeeper",
        )
        raw = ""
        for block in msg.content:
            if hasattr(block, "text"):
                raw = block.text
                break

        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        data: dict[str, Any] = json.loads(raw)
        return SafetyResult(
            ok=bool(data.get("ok", False)),
            text=str(data.get("text", text)),
            rewritten=bool(data.get("rewritten", False)),
            emergency=bool(data.get("emergency", False)),
            reason=data.get("reason"),
        )
    except Exception:
        return SafetyResult(
            ok=False, text="", rewritten=False, emergency=False, reason="gatekeeper_error"
        )


F = TypeVar("F")


def safety_gated(
    context: str = "telegram",
    agent: str = "unknown",
) -> Callable[[Callable[..., Coroutine[Any, Any, str]]], Callable[..., Coroutine[Any, Any, str]]]:
    """Decorator: gates the string return value of an async function through the safety check.

    If ok=False the decorator raises ValueError so callers can handle downstream.
    If emergency=True the original text is returned unchanged and the caller receives a
    SafetyResult with emergency=True via __saath_safety__ attribute on the exception.
    """

    def decorator(
        fn: Callable[..., Coroutine[Any, Any, str]],
    ) -> Callable[..., Coroutine[Any, Any, str]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> str:
            result_text: str = await fn(*args, **kwargs)
            raw_sid = kwargs.get("senior_id")
            senior_id: uuid.UUID | None = (
                uuid.UUID(str(raw_sid)) if isinstance(raw_sid, (str, uuid.UUID)) else None
            )
            safety = await check(result_text, context=context, agent=agent, senior_id=senior_id)
            if safety.emergency:
                return safety.text
            if not safety.ok:
                exc = ValueError(f"safety_gated blocked: {safety.reason}")
                exc.__saath_safety__ = safety  # type: ignore[attr-defined]
                raise exc
            return safety.text

        return wrapper

    return decorator
