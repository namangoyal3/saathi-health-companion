# DDISubAgent

## Purpose
Pharmacological safety analysis. Detects drug-drug interactions, drug-lab interactions, and drug-symptom correlations for a senior's active medication regimen. Produces structured HIGH/MEDIUM/LOW flags with reasoning traces visible in Langfuse. This is the demo centerpiece for the hackathon.

## Model
`claude-opus-4-7` — adaptive thinking, effort=`xhigh`, display=`"summarized"`

```python
response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=4096,
    thinking={"type": "adaptive", "display": "summarized"},
    output_config={"effort": "xhigh"},
    tools=[{"type": "memory_20250818", "name": "memory"}, ...],
    messages=[...],
    metadata={"agent": "DDISubAgent", "senior_id": str(senior_id)},
)
```

`type:"enabled"` with `budget_tokens` is **rejected** with HTTP 400 on Opus 4.7. Use the shape above exactly.

## Input Schema (DDI_INPUT_V1)

```json
{
  "senior_id": "uuid",
  "medications": [
    {
      "name": "string",
      "dose_mg": "number",
      "frequency_rrule": "string",
      "route": "oral|topical|inhaled|iv",
      "start_date": "YYYY-MM-DD",
      "prescriber": "string"
    }
  ],
  "recent_labs": [
    {
      "panel_date": "YYYY-MM-DD",
      "biomarkers": {
        "eGFR": 58,
        "HbA1c": 7.2,
        "TSH": 2.1
      }
    }
  ],
  "recent_symptoms": [
    {
      "date": "YYYY-MM-DD",
      "symptom": "string",
      "source": "ivr|telegram|family"
    }
  ]
}
```

## Output Schema (DDI_OUTPUT_V1)

```json
{
  "flags": [
    {
      "flag_id": "uuid",
      "severity": "HIGH|MEDIUM|LOW",
      "interaction_type": "drug_drug|drug_lab|drug_symptom",
      "drugs_involved": ["string"],
      "finding": "string (≤2 sentences, no diagnosis language)",
      "literature_basis": "string",
      "recommended_action": "string (discuss with physician)",
      "corroborating_events": ["symptom or lab references"]
    }
  ],
  "reasoning_summary": "string (≤3 sentences, the adaptive thinking summary)",
  "analysis_date": "ISO-8601 timestamp",
  "senior_id": "uuid"
}
```

## Canonical Demo Output (Lakshmi Iyer)

```json
{
  "flags": [
    {
      "flag_id": "...",
      "severity": "HIGH",
      "interaction_type": "drug_lab",
      "drugs_involved": ["Metformin 500mg"],
      "finding": "eGFR has declined from 78 to 58 over four quarters; Metformin is generally avoided below eGFR 45 and requires monitoring below 60.",
      "literature_basis": "ADA Standards of Care 2024, Section 9.3; FDA Metformin label (2016 revision).",
      "recommended_action": "Physician review recommended to assess whether dose adjustment is indicated given the declining eGFR trajectory.",
      "corroborating_events": ["Lab panel 2025-07-10: eGFR 58", "Lab panel 2025-04-08: eGFR 65", "Lab panel 2025-01-12: eGFR 71"]
    },
    {
      "flag_id": "...",
      "severity": "HIGH",
      "interaction_type": "drug_symptom",
      "drugs_involved": ["Amlodipine 5mg", "Telmisartan 40mg"],
      "finding": "Three episodes of post-morning-dose dizziness on April 4, 11, and 18 are associated with the combination of Amlodipine + Telmisartan in the published literature.",
      "literature_basis": "ESH/ESC Hypertension Guidelines 2023, orthostatic hypotension section.",
      "recommended_action": "Physician review recommended; consider BP measurement at 1h post-dose to assess orthostatic component.",
      "corroborating_events": ["Telegram 2025-04-04: 'dizzy after morning tablets'", "Telegram 2025-04-11: 'dizzy again'", "IVR 2025-04-18: reported dizziness"]
    }
  ],
  "reasoning_summary": "Analyzed 7 active medications against 4 quarterly lab panels and 5 symptom events. Two HIGH-severity findings identified: declining eGFR trajectory requiring Metformin vigilance, and a temporal cluster of post-morning-dose dizziness episodes consistent with Amlodipine+Telmisartan orthostatic hypotension.",
  "analysis_date": "2025-04-22T08:00:00Z",
  "senior_id": "00000000-0000-0000-0000-000000000001"
}
```

## System Prompt

```
You are DDISubAgent, a pharmacological safety analysis system for Saath, an AI health companion for elderly Indian patients.

ROLE
Analyze the provided medication list against recent lab values and reported symptoms. Identify drug-drug, drug-lab, and drug-symptom interactions. Produce structured, clinician-readable findings.

LANGUAGE RULES (non-negotiable)
- NEVER state diagnoses: forbidden = "you have CKD", "your kidneys are failing", "you are diabetic"
- ALLOWED: "eGFR has declined from X to Y", "associated with [drug] in the literature"
- NEVER prescribe or suggest dose changes: forbidden = "reduce Metformin to 250mg"
- ALLOWED: "physician review recommended to assess whether dose adjustment is indicated"
- NEVER use: "abnormal", "your test result", "your screening showed"
- NEVER give probability numbers for specific diseases
- Emergency symptoms (chest pain, severe breathlessness, stroke symptoms, fainting, acute severe injury, suicidal ideation) → set severity="HIGH", add emergency=true field, do not rewrite

SEVERITY CRITERIA
HIGH: Documented interaction with clinical evidence of harm or monitoring requirement; corroborated by ≥1 lab or symptom event
MEDIUM: Interaction documented in literature; no corroborating clinical event yet
LOW: Theoretical interaction; limited clinical evidence; informational only

OUTPUT
Respond ONLY with valid DDI_OUTPUT_V1 JSON. No prose before or after the JSON block.
```
