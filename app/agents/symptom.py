"""SymptomSubAgent — symptom clustering and temporal correlation analysis.

Detects recurring symptom patterns, post-dose correlations, and symptom escalation.
Uses Opus 4.7 medium effort.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.llm.opus import opus_call

_SYSTEM_PROMPT = """You are SymptomSubAgent, a symptom pattern analysis system for Saath.

ROLE
Analyze symptom reports from IVR and Telegram for a senior patient. Identify temporal
clusters, post-dose correlations, and escalation patterns.

KEY DETECTION RULES
1. Temporal cluster: ≥3 same-symptom reports within a 30-day window → flag MEDIUM
2. Post-dose correlation: symptom occurs within 2 hours of a medication timing → note correlation
3. Escalation: same symptom reported with increasing frequency over consecutive weeks → flag HIGH
4. Combination risk: dizziness + breathlessness together in any 7-day window → flag HIGH

LANGUAGE RULES
- NEVER diagnose the cause.
- ALLOWED: "Three episodes of dizziness reported on Apr 4, 11, 18, all within 2 hours of morning medications"
- ALLOWED: "Temporal correlation with Amlodipine+Telmisartan morning dose is noted in the literature"

OUTPUT
Call report_symptom_findings with all findings.
"""

_SYMPTOM_TOOL: dict[str, Any] = {
    "name": "report_symptom_findings",
    "description": "Report all identified symptom patterns and correlations.",
    "input_schema": {
        "type": "object",
        "required": ["findings", "summary"],
        "properties": {
            "summary": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["severity", "symptom", "finding", "recommended_action"],
                    "properties": {
                        "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "symptom": {"type": "string"},
                        "finding": {"type": "string"},
                        "event_dates": {"type": "array", "items": {"type": "string"}},
                        "correlated_medications": {"type": "array", "items": {"type": "string"}},
                        "recommended_action": {"type": "string"},
                    },
                },
            },
        },
    },
}


@dataclass
class SymptomFinding:
    severity: str
    symptom: str
    finding: str
    recommended_action: str
    event_dates: list[str] = field(default_factory=list)
    correlated_medications: list[str] = field(default_factory=list)


@dataclass
class SymptomResult:
    findings: list[SymptomFinding]
    summary: str
    senior_id: uuid.UUID


async def run(
    senior_id: uuid.UUID,
    symptoms: list[dict[str, Any]],
    medications: list[dict[str, Any]] | None = None,
) -> SymptomResult:
    """Analyze symptom reports for patterns and post-dose correlations.

    symptoms: list of {date, symptom, source, raw_text} rows.
    medications: optional list of {name, frequency_rrule} for correlation analysis.
    """
    payload: dict[str, Any] = {
        "senior_id": str(senior_id),
        "symptoms": symptoms,
    }
    if medications:
        payload["medications"] = medications

    msg = opus_call(
        system=_SYSTEM_PROMPT,
        user=json.dumps(payload),
        effort="medium",
        tools=[_SYMPTOM_TOOL],
        max_tokens=4096,
        senior_id=senior_id,
        agent_name="SymptomSubAgent",
        display="omitted",
    )

    raw_findings: list[dict[str, Any]] = []
    summary = ""

    for block in msg.content:
        if block.type == "tool_use" and block.name == "report_symptom_findings":
            data: dict[str, Any] = block.input
            raw_findings = data.get("findings", [])
            summary = data.get("summary", "")
            break

    findings = [
        SymptomFinding(
            severity=f["severity"],
            symptom=f["symptom"],
            finding=f["finding"],
            recommended_action=f["recommended_action"],
            event_dates=f.get("event_dates", []),
            correlated_medications=f.get("correlated_medications", []),
        )
        for f in raw_findings
    ]

    return SymptomResult(findings=findings, summary=summary, senior_id=senior_id)
