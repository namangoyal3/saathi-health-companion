"""VitalsAnomalyAgent — Haiku 4.5 classifier for wearable_daily_summary rows.

Separate from VitalsSubAgent (Opus 4.7 longitudinal summarizer). This agent fires
on each new daily summary from the Android companion app (or simulator),
classifies anomalies against per-marker thresholds, and returns safety-gatekeeper-
approved narratives.

Thresholds are baseline-relative where a baseline exists, absolute otherwise.
Never diagnoses, never suggests dose changes. Narratives are gated by
app.agents.safety.check() inside this module; the worker does NOT re-call gatekeeper.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from app.agents import safety
from app.llm.haiku import haiku_call

_SYSTEM_PROMPT = """You are VitalsAnomalyAgent, a wearable vitals anomaly classifier for Saath, an Indian eldercare AI health companion.

ROLE
Given one day's wearable summary (from Samsung Galaxy Watch or simulator) and the senior's recent baseline, identify anomalies using the threshold table. For each anomaly produce a short clinical narrative (1 sentence, ≤20 words).

THRESHOLD TABLE
avg_heart_rate (bpm):    MEDIUM >95 or <50  | HIGH >105 or <45   | URGENT >120 or <40
avg_spo2_pct (%):        MEDIUM <95         | HIGH <93           | URGENT <90
steps (daily):           MEDIUM <2000       | (no HIGH/URGENT)
sleep_minutes:           MEDIUM <300 (<5h)  | HIGH <240 (<4h)    | (no URGENT)
avg_skin_temp_c:         MEDIUM deviation ≥0.5°C from baseline
hrv_rmssd (ms):          MEDIUM <20         | HIGH <15           | (no URGENT)
stress_score (0-100):    MEDIUM >70         | HIGH >85           | (no URGENT)

LANGUAGE RULES (non-negotiable)
- NEVER diagnose: forbidden = "you have hypoxia", "cardiac arrhythmia", "abnormal"
- NEVER suggest dose changes or medications
- Use objective values only: "SpO₂ averaged 88% yesterday, below the 90% threshold"
- Emergency symptoms → still classify, still use threshold language

OUTPUT
You MUST call classify_anomalies with a valid anomaly list. Return empty list if no anomalies.
"""

_TOOL: dict[str, Any] = {
    "name": "classify_anomalies",
    "description": "Return all detected anomalies for this daily wearable summary.",
    "input_schema": {
        "type": "object",
        "required": ["anomalies"],
        "properties": {
            "anomalies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "marker",
                        "severity",
                        "value",
                        "threshold",
                        "narrative",
                    ],
                    "properties": {
                        "marker": {
                            "type": "string",
                            "enum": [
                                "avg_heart_rate",
                                "avg_spo2_pct",
                                "steps",
                                "sleep_minutes",
                                "avg_skin_temp_c",
                                "hrv_rmssd",
                                "stress_score",
                            ],
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["MEDIUM", "HIGH", "URGENT"],
                        },
                        "value": {"type": "number"},
                        "threshold": {"type": "number"},
                        "narrative": {"type": "string"},
                    },
                },
            }
        },
    },
}


@dataclass
class DailySummaryInput:
    """Daily wearable summary row (mirrors wearable_daily_summary schema)."""

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
    severity: str
    value: float
    threshold: float
    narrative: str


async def run(
    summary: DailySummaryInput,
    *,
    baseline_skin_temp_c: float | None = None,
) -> list[VitalsAnomaly]:
    """Classify one daily summary. Returns empty list if all within normal thresholds.

    Safety-gatekeeper is called inside this function on each narrative.
    Callers should not gate narratives again.
    """
    payload = {
        "senior_id": str(summary.senior_id),
        "date": summary.date,
        "summary": {
            "steps": summary.steps,
            "avg_heart_rate": summary.avg_heart_rate,
            "sleep_minutes": summary.sleep_minutes,
            "sleep_efficiency_pct": summary.sleep_efficiency_pct,
            "sleep_score": summary.sleep_score,
            "avg_spo2_pct": summary.avg_spo2_pct,
            "avg_skin_temp_c": summary.avg_skin_temp_c,
            "hrv_rmssd": summary.hrv_rmssd,
            "stress_score": summary.stress_score,
            "exercise_minutes": summary.exercise_minutes,
        },
        "baseline": {
            "skin_temp_c": baseline_skin_temp_c,
        },
    }

    msg = haiku_call(
        system=_SYSTEM_PROMPT,
        user=json.dumps(payload, ensure_ascii=False),
        tools=[_TOOL],
        max_tokens=1024,
        senior_id=summary.senior_id,
        agent_name="VitalsAnomalyAgent",
    )

    raw_anomalies: list[dict[str, Any]] = []
    for block in msg.content:
        if block.type == "tool_use" and block.name == "classify_anomalies":
            raw_anomalies = block.input.get("anomalies", [])
            break

    results: list[VitalsAnomaly] = []
    for a in raw_anomalies:
        gated = await safety.check(
            text=a["narrative"],
            context="vitals",
            agent="VitalsAnomalyAgent",
            senior_id=summary.senior_id,
        )
        narrative = (
            gated.text
            if gated.ok
            else f"{a['marker']} value {a['value']} noted; physician review recommended"
        )
        results.append(
            VitalsAnomaly(
                marker=a["marker"],
                severity=a["severity"],
                value=float(a["value"]),
                threshold=float(a["threshold"]),
                narrative=narrative,
            )
        )

    return results
