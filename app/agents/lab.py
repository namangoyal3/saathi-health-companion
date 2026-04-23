"""LabSubAgent — longitudinal lab trend analysis using Opus 4.7.

Detects eGFR decline rate, HbA1c trajectory, TSH drift, and other multi-quarter
biomarker trends. Returns structured findings for the report supervisor.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.llm.opus import opus_call

_SYSTEM_PROMPT = """You are LabSubAgent, a longitudinal biomarker analysis system for Saath.

ROLE
Analyze quarterly lab panels for a senior patient. Identify clinically significant trends.

KEY DETECTION RULES
1. eGFR decline: flag as HIGH if decline ≥ 3 mL/min/1.73m² per quarter over 3+ quarters
2. HbA1c: flag if > 7.5% (MEDIUM) or consistently rising trend (MEDIUM)
3. TSH: flag if outside 0.4-4.0 mIU/L range (MEDIUM)
4. Creatinine rising trend: flag if increased > 0.2 mg/dL over 2 consecutive panels (MEDIUM)

LANGUAGE RULES
- NEVER diagnose. Use objective values and trends only.
- NEVER suggest dose changes.
- ALLOWED: "eGFR has declined from 78 to 58 over four quarters (-5/quarter)"

OUTPUT
Call report_lab_findings with all findings.
"""

_LAB_TOOL: dict[str, Any] = {
    "name": "report_lab_findings",
    "description": "Report all identified lab trend findings.",
    "input_schema": {
        "type": "object",
        "required": ["findings", "summary"],
        "properties": {
            "summary": {"type": "string"},
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["severity", "biomarker", "finding", "recommended_action"],
                    "properties": {
                        "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "biomarker": {"type": "string"},
                        "finding": {"type": "string"},
                        "trend_data": {"type": "array", "items": {"type": "object"}},
                        "recommended_action": {"type": "string"},
                    },
                },
            },
        },
    },
}


@dataclass
class LabFinding:
    severity: str
    biomarker: str
    finding: str
    recommended_action: str
    trend_data: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class LabResult:
    findings: list[LabFinding]
    summary: str
    senior_id: uuid.UUID


async def run(
    senior_id: uuid.UUID,
    lab_panels: list[dict[str, Any]],
) -> LabResult:
    """Analyze longitudinal lab panels for trends.

    lab_panels: list of {panel_date, biomarkers: {name: value}} sorted by date asc.
    """
    payload = {
        "senior_id": str(senior_id),
        "lab_panels": lab_panels,
    }

    msg = opus_call(
        system=_SYSTEM_PROMPT,
        user=json.dumps(payload),
        effort="high",
        tools=[_LAB_TOOL],
        max_tokens=4096,
        senior_id=senior_id,
        agent_name="LabSubAgent",
        display="omitted",
    )

    raw_findings: list[dict[str, Any]] = []
    summary = ""

    for block in msg.content:
        if block.type == "tool_use" and block.name == "report_lab_findings":
            data: dict[str, Any] = block.input
            raw_findings = data.get("findings", [])
            summary = data.get("summary", "")
            break

    findings = [
        LabFinding(
            severity=f["severity"],
            biomarker=f["biomarker"],
            finding=f["finding"],
            recommended_action=f["recommended_action"],
            trend_data=f.get("trend_data", []),
        )
        for f in raw_findings
    ]

    return LabResult(findings=findings, summary=summary, senior_id=senior_id)
