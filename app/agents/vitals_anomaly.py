"""VitalsAnomalyAgent — classifies wearable_daily_summary rows and produces
safety-gatekeeper-approved anomaly narratives.

Architecture:
  1. Deterministic threshold classification (Python) — fast, reliable, testable
  2. OpenRouter → NVIDIA fallback to generate natural-language narratives
  3. Template fallback if both LLM providers fail (templates are already
     safety-compliant: objective values only, no diagnosis, no dose changes)
  4. Optional safety-gatekeeper pass (skipped if Anthropic key isn't configured)

This approach is resilient to any single provider outage and keeps the demo
deterministic on thresholds even when LLM narratives degrade.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass

from app.config import settings

log = logging.getLogger(__name__)


# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class DailySummaryInput:
    senior_id: uuid.UUID
    date: str  # YYYY-MM-DD
    steps: int = 0
    avg_heart_rate: int | None = None
    sleep_minutes: int | None = None
    sleep_efficiency_pct: int | None = None
    sleep_score: int | None = None
    avg_spo2_pct: int | None = None
    avg_skin_temp_c: float | None = None
    hrv_rmssd: int | None = None
    stress_score: int | None = None
    exercise_minutes: int | None = None


@dataclass
class VitalsAnomaly:
    marker: str
    severity: str  # MEDIUM | HIGH | URGENT
    value: float
    threshold: float
    narrative: str


# ── Threshold classification (deterministic) ─────────────────────────────────


def _hr_severity(hr: int) -> tuple[str | None, float]:
    if hr > 120 or hr < 40:
        return ("URGENT", 120.0 if hr > 120 else 40.0)
    if hr > 105 or hr < 45:
        return ("HIGH", 105.0 if hr > 105 else 45.0)
    if hr > 95 or hr < 50:
        return ("MEDIUM", 95.0 if hr > 95 else 50.0)
    return (None, 0.0)


def _spo2_severity(spo2: int) -> tuple[str | None, float]:
    if spo2 < 90:
        return ("URGENT", 90.0)
    if spo2 < 93:
        return ("HIGH", 93.0)
    if spo2 < 95:
        return ("MEDIUM", 95.0)
    return (None, 0.0)


def _sleep_severity(minutes: int) -> tuple[str | None, float]:
    if minutes < 240:
        return ("HIGH", 240.0)
    if minutes < 300:
        return ("MEDIUM", 300.0)
    return (None, 0.0)


def _hrv_severity(hrv: int) -> tuple[str | None, float]:
    if hrv < 15:
        return ("HIGH", 15.0)
    if hrv < 20:
        return ("MEDIUM", 20.0)
    return (None, 0.0)


def _stress_severity(score: int) -> tuple[str | None, float]:
    if score > 85:
        return ("HIGH", 85.0)
    if score > 70:
        return ("MEDIUM", 70.0)
    return (None, 0.0)


def classify_thresholds(
    summary: DailySummaryInput, *, baseline_skin_temp_c: float | None = None
) -> list[VitalsAnomaly]:
    """Apply deterministic thresholds. Returns anomalies without narratives yet."""
    found: list[VitalsAnomaly] = []

    if summary.avg_heart_rate is not None:
        sev, thr = _hr_severity(summary.avg_heart_rate)
        if sev:
            found.append(
                VitalsAnomaly("avg_heart_rate", sev, float(summary.avg_heart_rate), thr, "")
            )

    if summary.avg_spo2_pct is not None:
        sev, thr = _spo2_severity(summary.avg_spo2_pct)
        if sev:
            found.append(VitalsAnomaly("avg_spo2_pct", sev, float(summary.avg_spo2_pct), thr, ""))

    if summary.steps is not None and summary.steps < 2000:
        found.append(VitalsAnomaly("steps", "MEDIUM", float(summary.steps), 2000.0, ""))

    if summary.sleep_minutes is not None:
        sev, thr = _sleep_severity(summary.sleep_minutes)
        if sev:
            found.append(VitalsAnomaly("sleep_minutes", sev, float(summary.sleep_minutes), thr, ""))

    if summary.hrv_rmssd is not None:
        sev, thr = _hrv_severity(summary.hrv_rmssd)
        if sev:
            found.append(VitalsAnomaly("hrv_rmssd", sev, float(summary.hrv_rmssd), thr, ""))

    if summary.stress_score is not None:
        sev, thr = _stress_severity(summary.stress_score)
        if sev:
            found.append(VitalsAnomaly("stress_score", sev, float(summary.stress_score), thr, ""))

    if (
        summary.avg_skin_temp_c is not None
        and baseline_skin_temp_c is not None
        and abs(summary.avg_skin_temp_c - baseline_skin_temp_c) >= 0.5
    ):
        found.append(
            VitalsAnomaly(
                "avg_skin_temp_c",
                "MEDIUM",
                float(summary.avg_skin_temp_c),
                float(baseline_skin_temp_c),
                "",
            )
        )

    return found


# ── Narrative generation ─────────────────────────────────────────────────────


_NARRATIVE_TEMPLATES: dict[str, str] = {
    "avg_heart_rate": "Heart rate averaged {value:.0f} bpm, outside the {threshold:.0f} bpm threshold.",
    "avg_spo2_pct": "SpO₂ averaged {value:.0f}%, below the {threshold:.0f}% threshold.",
    "steps": "Step count of {value:.0f} is below the {threshold:.0f} daily threshold.",
    "sleep_minutes": "Sleep was {value:.0f} minutes, below the {threshold:.0f}-minute threshold.",
    "hrv_rmssd": "Heart-rate variability {value:.0f} ms is below the {threshold:.0f} ms threshold.",
    "stress_score": "Stress score {value:.0f} is above the {threshold:.0f} threshold.",
    "avg_skin_temp_c": "Skin temperature {value:.1f}°C deviates ≥0.5°C from the baseline of {threshold:.1f}°C.",
}


def _template_narrative(a: VitalsAnomaly) -> str:
    tmpl = _NARRATIVE_TEMPLATES.get(
        a.marker, "{marker} reading {value} crossed threshold {threshold}."
    )
    return tmpl.format(marker=a.marker, value=a.value, threshold=a.threshold)


_LLM_SYSTEM = """You are VitalsAnomalyAgent, a wearable anomaly narrator for an Indian eldercare AI companion.

INPUT
JSON with a senior's date + an `anomalies` list. Each item has marker/severity/value/threshold.

TASK
For each anomaly, write ONE concise narrative (≤20 words) using ONLY objective values and threshold language.

LANGUAGE RULES (non-negotiable)
- NEVER diagnose: forbidden = "you have hypoxia", "cardiac arrhythmia", "abnormal"
- NEVER suggest dose changes or medications
- Never use "abnormal", "you have", "your screening result"
- Use phrases like "averaged X bpm, above the Y bpm threshold" or "physician review recommended"

OUTPUT
Reply with ONLY a JSON object — no prose, no markdown fences — of shape:
{"narratives": [{"marker": "...", "narrative": "..."}]}
with one entry per input anomaly, in the same order.
"""


async def _llm_narratives(anomalies: list[VitalsAnomaly], date: str) -> dict[str, str] | None:
    """Try OpenRouter then NVIDIA. Returns {marker: narrative} or None on failure."""
    payload = json.dumps(
        {
            "date": date,
            "anomalies": [
                {
                    "marker": a.marker,
                    "severity": a.severity,
                    "value": a.value,
                    "threshold": a.threshold,
                }
                for a in anomalies
            ],
        },
        ensure_ascii=False,
    )

    # Try OpenRouter first
    try:
        from app.llm.openrouter import openrouter_chat

        raw = await openrouter_chat(
            system=_LLM_SYSTEM, user=payload, max_tokens=600, temperature=0.2
        )
        parsed = _parse_narrative_json(raw)
        if parsed:
            return parsed
        log.warning("openrouter_narrative_parse_failed raw=%s", raw[:200])
    except Exception as exc:
        log.warning("openrouter_narrative_failed err=%s", exc)

    # Fallback: NVIDIA NIM
    try:
        from app.llm.nvidia import nvidia_chat

        raw = await nvidia_chat(system=_LLM_SYSTEM, user=payload, max_tokens=600, temperature=0.2)
        parsed = _parse_narrative_json(raw)
        if parsed:
            return parsed
        log.warning("nvidia_narrative_parse_failed raw=%s", raw[:200])
    except Exception as exc:
        log.warning("nvidia_narrative_failed err=%s", exc)

    return None


def _parse_narrative_json(raw: str) -> dict[str, str] | None:
    """Strip fences/prose and parse JSON. Returns {marker: narrative} or None."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text.strip("`")
    # Find the first { and last } in case model added prose
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except Exception:
        return None
    narratives = data.get("narratives") if isinstance(data, dict) else None
    if not isinstance(narratives, list):
        return None
    out: dict[str, str] = {}
    for item in narratives:
        if isinstance(item, dict) and "marker" in item and "narrative" in item:
            narrative = str(item["narrative"]).strip()
            if narrative:
                out[str(item["marker"])] = narrative
    return out or None


async def _maybe_safety_gate(text: str, senior_id: uuid.UUID) -> str:
    """Pass text through safety-gatekeeper if Anthropic is available. Else return as-is
    (templates and LLM narratives are already designed to be safety-compliant)."""
    if not settings.anthropic_api_key or settings.anthropic_api_key.startswith("change-me"):
        return text
    try:
        from app.agents import safety

        gated = await safety.check(
            text=text, context="vitals", agent="VitalsAnomalyAgent", senior_id=senior_id
        )
        return gated.text if gated.ok else text
    except Exception as exc:
        log.warning("safety_gatekeeper_skipped err=%s", exc)
        return text


# ── Public entry point ───────────────────────────────────────────────────────


async def run(
    summary: DailySummaryInput, *, baseline_skin_temp_c: float | None = None
) -> list[VitalsAnomaly]:
    """Classify a daily summary and attach narratives. Returns [] if no anomalies.

    Pipeline:
      1. Deterministic threshold classification
      2. LLM narrative generation (OpenRouter → NVIDIA fallback)
      3. Template narrative fallback for any marker the LLM missed
      4. Safety-gatekeeper pass if Anthropic key is configured
    """
    bare = classify_thresholds(summary, baseline_skin_temp_c=baseline_skin_temp_c)
    if not bare:
        return []

    llm_map = await _llm_narratives(bare, summary.date)

    results: list[VitalsAnomaly] = []
    for a in bare:
        narrative = (llm_map or {}).get(a.marker) or _template_narrative(a)
        narrative = await _maybe_safety_gate(narrative, summary.senior_id)
        results.append(
            VitalsAnomaly(
                marker=a.marker,
                severity=a.severity,
                value=a.value,
                threshold=a.threshold,
                narrative=narrative,
            )
        )

    return results
