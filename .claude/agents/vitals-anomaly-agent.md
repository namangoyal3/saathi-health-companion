# VitalsAnomalyAgent

**Distinct from** `vitals-subagent.md` (Opus 4.7 longitudinal summarizer, feeds
daily brief + Doctor Visit Report). This agent is the **anomaly detector** —
fires on each new `wearable_daily_summary` row, classifies markers against
thresholds, and produces safety-gatekeeper-approved narratives.

## Purpose
Classify one daily wearable summary (Samsung Galaxy Watch via
[`app/api/wearable.py`](../../app/api/wearable.py) or the simulator at
`/vitals-simulator`) and return zero or more anomaly results per marker.

## Model
`claude-haiku-4-5-20251001` — thinking off, tool-forced.

## Effort
n/a (Haiku; no thinking).

## Input Schema
```json
{
  "senior_id": "uuid",
  "date": "YYYY-MM-DD",
  "summary": {
    "steps": int,
    "avg_heart_rate": int | null,
    "sleep_minutes": int | null,
    "sleep_efficiency_pct": int | null,
    "sleep_score": int | null,
    "avg_spo2_pct": int | null,
    "avg_skin_temp_c": float | null,
    "hrv_rmssd": int | null,
    "stress_score": int | null,
    "exercise_minutes": int | null
  },
  "baseline": {
    "skin_temp_c": float | null
  }
}
```

## Output Schema
`list[VitalsAnomaly]` — each anomaly has `marker, severity, value, threshold, narrative`.
Returns empty list if the reading is within normal thresholds.

## Thresholds
| Marker | MEDIUM | HIGH | URGENT |
|--------|--------|------|--------|
| `avg_heart_rate` (bpm) | >95 or <50 | >105 or <45 | >120 or <40 |
| `avg_spo2_pct` (%) | <95 | <93 | <90 |
| `steps` (daily) | <2000 | — | — |
| `sleep_minutes` | <300 | <240 | — |
| `avg_skin_temp_c` | ≥0.5°C from baseline | — | — |
| `hrv_rmssd` (ms) | <20 | <15 | — |
| `stress_score` (0–100) | >70 | >85 | — |

## Safety Contract
Safety-gatekeeper (`app/agents/safety.check()`) is called **inside**
`app/agents/vitals_anomaly.run()` on every narrative before it is returned.
The worker (`app/workers/vitals_anomaly.process_summary()`) does **not**
re-gate narratives. Gate once, at the agent boundary.

## Samsung / Phase-2 Extensibility
This agent consumes the `DailySummaryInput` dataclass, which mirrors
`wearable_daily_summary` — the canonical daily-rollup format. The Android
companion app (`android/saath-companion/`) already posts this format to
`POST /wearable/samsung/webhook` with HMAC-SHA256 signatures. The simulator
at `/vitals-simulator` posts identical payloads. **No agent changes are needed**
when swapping simulator for real watch — the ingress surface is shared.

To add a new wearable brand (Fitbit, Apple Watch):
1. Add a webhook endpoint that maps the brand's payload → `WearableDailySummary`.
2. Insert into `wearable_daily_summary`.
3. Call `process_summary(senior_id, date)`.
Zero changes to this agent.

## Caller
- `app/api/wearable.py:samsung_webhook()` — calls inline for ≤5s demo latency
- `app/workers/vitals_anomaly.detect_vitals_anomalies()` — arq background task

## Metadata (Langfuse)
`{"agent": "VitalsAnomalyAgent", "senior_id": "<uuid>"}`

## TODO
- Per-senior HR baseline (currently only skin-temp baseline is baseline-relative)
- Weekend vs weekday step-count baseline
- Time-of-day HR patterns (post-AM-medication spike detection)
