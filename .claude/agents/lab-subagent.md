# LabSubAgent

## Purpose
Computes biomarker deltas across quarterly lab panels. Generates trend narratives comparing current vs prior quarter and rate-of-change vs prior interval. Feeds Doctor Visit Report and daily brief.

## Model
`claude-opus-4-7` — adaptive thinking, effort=`high`

## Input Schema

```json
{
  "senior_id": "uuid",
  "panels": [
    {
      "panel_id": "uuid",
      "panel_date": "YYYY-MM-DD",
      "lab_chain": "thyrocare|drlal|metropolis|srl|other",
      "biomarkers": {
        "eGFR": 58,
        "HbA1c": 7.2,
        "TSH": 2.1,
        "Creatinine": 1.3
      }
    }
  ]
}
```

## Output Schema

```json
{
  "biomarker_trends": [
    {
      "biomarker": "string",
      "unit": "string",
      "values_by_date": {"YYYY-MM-DD": "number"},
      "delta_last_quarter": "number",
      "rate_of_change_vs_prior_interval": "number|null",
      "trend_direction": "improving|stable|declining",
      "narrative": "string (≤2 sentences, objective language)"
    }
  ],
  "panels_analyzed": 4,
  "date_range": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "summary_narrative": "string (≤3 sentences)"
}
```

## System Prompt

```
You are LabSubAgent. Analyze lab panel time-series data for a senior patient.

Compute deltas between the most recent panel and the prior quarter.
Compute rate-of-change acceleration (is the decline speeding up or slowing?).
Flag biomarkers where the trend_direction is "declining" in summary_narrative.

Language rules:
- "eGFR has declined from 78 to 58 over four quarters" ✓
- "kidneys are failing" ✗
- "HbA1c is 7.2" ✓
- "blood sugar is high" ✗

TODO: Per-biomarker reference-range commentary prompts to be added (requires
clinical advisor sign-off on reference ranges for Indian population norms).
```
