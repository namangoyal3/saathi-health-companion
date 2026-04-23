# VitalsSubAgent

## Purpose
Processes wearable vitals streams (Phase 2: Samsung Health SDK). In Phase 1, reads fixture data from memory. Outputs BP trend, HR variability, SpO2 min, and step count weekly average. Feeds daily brief and Doctor Visit Report.

## Model
`claude-opus-4-7` — adaptive thinking, effort=`medium`

## Input Schema

```json
{
  "senior_id": "uuid",
  "lookback_days": 30,
  "data_source": "fixture|samsung_health|manual_entry"
}
```

Phase 1: `data_source` is always `"fixture"`. Phase 2: Samsung Health SDK webhook stream.

## Output Schema

```json
{
  "bp_trend": {
    "readings": [
      {"date": "YYYY-MM-DD", "systolic": 138, "diastolic": 86}
    ],
    "avg_systolic": 138,
    "avg_diastolic": 86,
    "trend": "stable|rising|falling"
  },
  "hr_variability": {
    "avg_resting_bpm": 72,
    "min_bpm": 58,
    "max_bpm": 110
  },
  "spo2_min": 96,
  "steps_weekly_avg": 4200,
  "narrative": "string (≤2 sentences)"
}
```

## System Prompt

```
You are VitalsSubAgent. Summarize wearable vitals data for a senior patient.

Phase 1: Data comes from fixture — treat it as real. Phase 2: Samsung Health SDK stream.
Report objective values only. No diagnosis. No alarming language.

"Blood pressure readings averaged 138/86 over the past 30 days." ✓
"Blood pressure is dangerously high." ✗

TODO: Phase 2 Samsung Health SDK webhook schema and OAuth flow to be documented.
TODO: BP reference ranges for age-adjusted Indian population norms pending clinical review.
```
