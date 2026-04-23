"""AdherenceSubAgent — medication adherence pattern analysis.

Detects missed-dose clusters, day-of-week patterns, and adherence rate per medication.
Uses Opus 4.7 medium effort.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.llm.opus import opus_call

_SYSTEM_PROMPT = """You are AdherenceSubAgent, a medication adherence analyst for Saath.

ROLE
Analyze medication reminder event history. Identify patterns: missed-dose clusters,
day-of-week skips, per-medication adherence rates.

KEY DETECTION RULES
1. Adherence rate: (taken events) / (taken + skipped + auto_skip) per medication per period
2. Day-of-week cluster: if ≥3 misses occur on the same day in a 30-day window, flag it
3. Time-of-day cluster: if morning-dose misses cluster around the same time, note it
4. Drug-specific risk: flag Metformin and Levothyroxine misses as MEDIUM (glycemic/thyroid impact)

LANGUAGE RULES
- NEVER diagnose. Report facts: "Metformin was missed on 4 occasions in the last 14 days"
- NEVER suggest changing the regimen.

OUTPUT
Call report_adherence_findings with all findings.
"""

_ADHERENCE_TOOL: dict[str, Any] = {
    "name": "report_adherence_findings",
    "description": "Report all identified adherence patterns.",
    "input_schema": {
        "type": "object",
        "required": ["findings", "overall_adherence_pct", "summary"],
        "properties": {
            "overall_adherence_pct": {"type": "number"},
            "summary": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["severity", "medication", "finding", "recommended_action"],
                    "properties": {
                        "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "medication": {"type": "string"},
                        "finding": {"type": "string"},
                        "adherence_pct": {"type": "number"},
                        "miss_dates": {"type": "array", "items": {"type": "string"}},
                        "recommended_action": {"type": "string"},
                    },
                },
            },
        },
    },
}


@dataclass
class AdherenceFinding:
    severity: str
    medication: str
    finding: str
    recommended_action: str
    adherence_pct: float = 0.0
    miss_dates: list[str] = field(default_factory=list)


@dataclass
class AdherenceResult:
    findings: list[AdherenceFinding]
    overall_adherence_pct: float
    summary: str
    senior_id: uuid.UUID


async def run(
    senior_id: uuid.UUID,
    reminder_events: list[dict[str, Any]],
) -> AdherenceResult:
    """Analyze medication reminder events for adherence patterns.

    reminder_events: list of {scheduled_for, medication_name, event} rows.
    """
    payload = {
        "senior_id": str(senior_id),
        "reminder_events": reminder_events,
    }

    msg = opus_call(
        system=_SYSTEM_PROMPT,
        user=json.dumps(payload),
        effort="medium",
        tools=[_ADHERENCE_TOOL],
        max_tokens=4096,
        senior_id=senior_id,
        agent_name="AdherenceSubAgent",
        display="omitted",
    )

    raw_findings: list[dict[str, Any]] = []
    overall_pct = 0.0
    summary = ""

    for block in msg.content:
        if block.type == "tool_use" and block.name == "report_adherence_findings":
            data: dict[str, Any] = block.input
            raw_findings = data.get("findings", [])
            overall_pct = float(data.get("overall_adherence_pct", 0.0))
            summary = data.get("summary", "")
            break

    findings = [
        AdherenceFinding(
            severity=f["severity"],
            medication=f["medication"],
            finding=f["finding"],
            recommended_action=f["recommended_action"],
            adherence_pct=float(f.get("adherence_pct", 0.0)),
            miss_dates=f.get("miss_dates", []),
        )
        for f in raw_findings
    ]

    return AdherenceResult(
        findings=findings,
        overall_adherence_pct=overall_pct,
        summary=summary,
        senior_id=senior_id,
    )
