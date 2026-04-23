# ReportSupervisor

## Purpose
Orchestrates the Doctor Visit Report 12-step pipeline. Fans out to 4 sub-agents (Adherence, Symptom, Lab, DDI) concurrently via asyncio.gather. Selects specialist template variant (GP, Nephrology, Endocrinology, Cardiology, Emergency). Synthesizes a 3-sentence exec summary. Routes exec summary through SafetyGatekeeper before persisting.

## Model
`claude-opus-4-7` — adaptive thinking, effort=`high`

Context editing (`context-management-2025-06-27`) is used for the synthesis step to clear tool results before the final narrative call. Requires `client.beta.messages.create()` not `client.messages.create()`.

## Input Schema

```json
{
  "senior_id": "uuid",
  "report_type": "gp|nephro|endo|cardio|emergency",
  "lookback_days": 90,
  "guardian_id": "uuid",
  "requesting_physician": "string|null"
}
```

## Output Schema

```json
{
  "report_id": "uuid",
  "exec_summary": "string (3 sentences, clinician-grade prose)",
  "sections": {
    "medications": {},
    "adherence": {},
    "labs": {},
    "symptoms": {},
    "ddi_flags": {},
    "vitals": {}
  },
  "template_variant": "gp|nephro|endo|cardio|emergency",
  "pdf_url": "string (signed R2 URL, 7-day TTL)",
  "generation_time_ms": 12400,
  "safety_gatekeeper_passed": true
}
```

## Pipeline Steps

1. Load senior profile from memory
2. Query medication list (Postgres)
3. Fan-out: asyncio.gather(AdherenceSubAgent, SymptomSubAgent, LabSubAgent, DDISubAgent)
4. Wait for all 4 sub-agent results
5. Select specialist template variant based on `report_type`
6. Synthesize exec summary (Opus 4.7, effort=high)
7. Route exec_summary through SafetyGatekeeper
8. Render HTML via Jinja2 template
9. WeasyPrint → PDF bytes
10. Upload to R2 → signed URL (7-day TTL)
11. Persist `doctor_report` row in Postgres
12. Emit SSE event `report.ready` to dashboard

## System Prompt

```
You are ReportSupervisor. Synthesize a clinician-grade Doctor Visit Report from
sub-agent outputs.

Write a 3-sentence executive summary:
- Sentence 1: Most significant finding (DDI flag or lab trend)
- Sentence 2: Adherence context
- Sentence 3: Recommended next steps (no dosage instructions)

Specialist variants collapse irrelevant sections:
- nephro: expand eGFR/Creatinine, collapse thyroid
- endo: expand HbA1c/TSH, collapse eGFR
- cardio: expand BP/HR, ECG if available; collapse lab section
- emergency: only DDI HIGH flags + emergency protocol

Language rules: objective findings only. No diagnoses. No probability numbers.
Run exec_summary through SafetyGatekeeper before including in output.

TODO: Synthesis prompt temperature and max_tokens to be tuned after first
end-to-end demo run on Lakshmi fixture.
```
