"""Deterministic emergency keyword guard — runs BEFORE any LLM call.

Free-tier models routinely ignore system-prompt safety rules. We cannot trust
the LLM to reliably surface emergency guidance when a senior reports something
acute. A regex match + canned reply is the safety net.

Shared by both /chat (web) and the Telegram bot's voice_agent.

English + Hindi patterns, word-boundary matched to avoid false positives like
"I have no chest pain" (Hindi: "सीने में दर्द नहीं है" — future TODO:
negation detection beyond whole-word matching).
"""

from __future__ import annotations

import re

_PATTERNS = [
    # English
    r"\bchest pain\b",
    r"\bsevere (?:breathlessness|shortness of breath)\b",
    r"\bcan'?t breathe\b",
    r"\bstroke\b",
    r"\bfainted?\b",
    r"\bfainting\b",
    r"\bunconscious\b",
    r"\bcollaps(?:e|ed|ing)\b",
    r"\bseizure\b",
    r"\bsuicid(?:e|al)\b",
    r"\bbleeding heavily\b",
    r"\bsevere bleeding\b",
    r"\bheart attack\b",
    # Hindi — emergency vocabulary that Lakshmi/Meera might send
    r"सीने\s*में\s*दर्द",  # chest pain
    r"साँस\s*नहीं",  # can't breathe
    r"बेहोश",  # unconscious/faint
    r"दौरा",  # attack/seizure
    r"दिल\s*का\s*दौरा",  # heart attack
    r"पक्षाघात",  # stroke/paralysis
]

EMERGENCY_RE = re.compile("|".join(_PATTERNS), re.IGNORECASE)

EMERGENCY_REPLY_EN = (
    "Please call emergency services at 112 immediately. "
    "If someone is with you, ask them to help you call."
)
EMERGENCY_REPLY_HI = "कृपया तुरंत 112 पर आपातकालीन सेवा को कॉल करें। अगर कोई आपके साथ है, तो उनकी मदद लें।"


def is_emergency(text: str) -> bool:
    """Return True if `text` contains any recognized emergency phrase."""
    return bool(EMERGENCY_RE.search(text or ""))


def emergency_reply(lang: str = "en") -> str:
    """Return the canned emergency reply in the requested language."""
    return EMERGENCY_REPLY_HI if (lang or "").lower() == "hi" else EMERGENCY_REPLY_EN
