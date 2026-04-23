"""DDISubAgent — drug-drug / drug-lab / drug-symptom interaction analysis.

Opus 4.7 with xhigh extended thinking + tool-forced DDI_OUTPUT_V1 schema.
Every run is traced in Langfuse via metadata tags.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.llm.opus import opus_call

_SYSTEM_PROMPT = """You are DDISubAgent, a pharmacological safety analysis system for Saath, an AI health companion for elderly Indian patients.

ROLE
Analyze the provided medication list against recent lab values and reported symptoms. Identify drug-drug, drug-lab, and drug-symptom interactions. Produce structured, clinician-readable findings.

LANGUAGE RULES (non-negotiable)
- NEVER state diagnoses: forbidden = "you have CKD", "your kidneys are failing", "you are diabetic"
- ALLOWED: "eGFR has declined from X to Y", "associated with [drug] in the literature"
- NEVER prescribe or suggest dose changes: forbidden = "reduce Metformin to 250mg"
- ALLOWED: "physician review recommended to assess whether dose adjustment is indicated"
- NEVER use: "abnormal", "your test result", "your screening showed"
- NEVER give probability numbers for specific diseases
- Emergency symptoms (chest pain, severe breathlessness, stroke symptoms, fainting, acute severe injury, suicidal ideation) → set severity="HIGH"

SEVERITY CRITERIA
HIGH: Documented interaction with clinical evidence of harm or monitoring requirement; corroborated by ≥1 lab or symptom event
MEDIUM: Interaction documented in literature; no corroborating clinical event yet
LOW: Theoretical interaction; limited clinical evidence; informational only

OUTPUT
You MUST call the report_interactions tool with valid DDI_OUTPUT_V1 data. No prose before or after."""

_DDI_OUTPUT_TOOL: dict[str, Any] = {
    "name": "report_interactions",
    "description": "Report all identified drug interactions in DDI_OUTPUT_V1 schema.",
    "input_schema": {
        "type": "object",
        "required": ["flags", "reasoning_summary"],
        "properties": {
            "flags": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "severity",
                        "interaction_type",
                        "drugs_involved",
                        "finding",
                        "literature_basis",
                        "recommended_action",
                        "corroborating_events",
                    ],
                    "properties": {
                        "severity": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        "interaction_type": {
                            "type": "string",
                            "enum": ["drug_drug", "drug_lab", "drug_symptom"],
                        },
                        "drugs_involved": {"type": "array", "items": {"type": "string"}},
                        "finding": {"type": "string"},
                        "literature_basis": {"type": "string"},
                        "recommended_action": {"type": "string"},
                        "corroborating_events": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "reasoning_summary": {"type": "string"},
        },
    },
}


@dataclass
class MedicationInput:
    name: str
    dose_mg: Decimal | float
    frequency_rrule: str
    route: str = "oral"
    start_date: str = ""
    prescriber: str = ""


@dataclass
class LabPanelInput:
    panel_date: str
    biomarkers: dict[str, float]


@dataclass
class SymptomInput:
    date: str
    symptom: str
    source: str


@dataclass
class DDIInput:
    senior_id: uuid.UUID
    medications: list[MedicationInput]
    recent_labs: list[LabPanelInput]
    recent_symptoms: list[SymptomInput] = field(default_factory=list)


@dataclass
class DDIFlag:
    flag_id: str
    severity: str
    interaction_type: str
    drugs_involved: list[str]
    finding: str
    literature_basis: str
    recommended_action: str
    corroborating_events: list[str]


@dataclass
class DDIResult:
    flags: list[DDIFlag]
    reasoning_summary: str
    analysis_date: str
    senior_id: uuid.UUID


async def run(ddi_input: DDIInput) -> DDIResult:
    """Run DDI analysis for a senior's medication regimen.

    Uses tool-forced output to guarantee DDI_OUTPUT_V1 schema compliance.
    Extended thinking (xhigh) makes the pharmacology reasoning visible in Langfuse.
    """
    payload = {
        "senior_id": str(ddi_input.senior_id),
        "medications": [
            {
                "name": m.name,
                "dose_mg": float(m.dose_mg),
                "frequency_rrule": m.frequency_rrule,
                "route": m.route,
                "start_date": m.start_date,
                "prescriber": m.prescriber,
            }
            for m in ddi_input.medications
        ],
        "recent_labs": [
            {"panel_date": lab.panel_date, "biomarkers": lab.biomarkers}
            for lab in ddi_input.recent_labs
        ],
        "recent_symptoms": [
            {"date": s.date, "symptom": s.symptom, "source": s.source}
            for s in ddi_input.recent_symptoms
        ],
    }

    msg = opus_call(
        system=_SYSTEM_PROMPT,
        user=json.dumps(payload, ensure_ascii=False),
        effort="xhigh",
        tools=[_DDI_OUTPUT_TOOL],
        max_tokens=4096,
        senior_id=ddi_input.senior_id,
        agent_name="DDISubAgent",
        display="summarized",
    )

    # Extract tool use block
    raw_flags: list[dict[str, Any]] = []
    reasoning_summary = ""

    for block in msg.content:
        if block.type == "tool_use" and block.name == "report_interactions":
            data: dict[str, Any] = block.input
            raw_flags = data.get("flags", [])
            reasoning_summary = data.get("reasoning_summary", "")
            break
        if block.type == "thinking":
            # Adaptive thinking summary — captured in Langfuse via metadata
            pass

    flags = [
        DDIFlag(
            flag_id=str(uuid.uuid4()),
            severity=f["severity"],
            interaction_type=f["interaction_type"],
            drugs_involved=f["drugs_involved"],
            finding=f["finding"],
            literature_basis=f["literature_basis"],
            recommended_action=f["recommended_action"],
            corroborating_events=f.get("corroborating_events", []),
        )
        for f in raw_flags
    ]

    return DDIResult(
        flags=flags,
        reasoning_summary=reasoning_summary,
        analysis_date=datetime.now(UTC).isoformat(),
        senior_id=ddi_input.senior_id,
    )
