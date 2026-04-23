# AdherenceSubAgent

## Purpose
Computes per-drug adherence rates for a senior's active medication regimen. Detects day-of-week miss clusters (e.g., Tue/Wed pattern for Lakshmi). Feeds into the daily brief and Doctor Visit Report.

## Model
`claude-opus-4-7` — adaptive thinking, effort=`medium`

## Input Schema

```json
{
  "senior_id": "uuid",
  "lookback_days": 30,
  "medications": [
    {
      "medication_id": "uuid",
      "name": "string",
      "dose_mg": "number",
      "frequency_rrule": "string"
    }
  ]
}
```

Data source: `med_reminder_event` table filtered by `senior_id` and `scheduled_for >= NOW() - lookback_days`.

## Output Schema

```json
{
  "overall_adherence_pct": 87,
  "by_drug": [
    {
      "medication_id": "uuid",
      "name": "string",
      "doses_scheduled": 30,
      "doses_taken": 26,
      "adherence_pct": 87,
      "miss_pattern": "string|null"
    }
  ],
  "day_of_week_clusters": [
    {
      "day": "Tuesday|Wednesday|...",
      "miss_count": 3,
      "drugs": ["string"]
    }
  ],
  "narrative": "string (≤2 sentences, no diagnosis language)"
}
```

## System Prompt

```
You are AdherenceSubAgent. Analyze medication reminder events for a senior patient.

Compute adherence rates per drug and overall. Detect day-of-week miss clusters.
Report in the output schema only. Use only objective language — no diagnosis,
no dosage suggestions. If adherence_pct < 80% for any drug, flag it in narrative
with neutral phrasing: "Adherence to [drug] was [pct]% over the past [N] days."

TODO: Clustering algorithm details to be confirmed in Tech Spec update.
```
