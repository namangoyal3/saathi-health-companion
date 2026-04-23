# Smartwatch Markers Detector — Design Spec
**Date:** 2026-04-23
**Status:** Approved for implementation
**Hackathon deadline:** 2026-04-26 20:00 EST

---

## 1. Summary

Build the missing **VitalsSubAgent** (PRD §6.3 R3.3, Phase 1) plus a **watch simulator web UI** that lets a demo operator send named clinical scenarios from a browser. Anomaly flags route to Priya via Telegram, are injected into Lakshmi's memory store, and feed the existing daily brief pipeline.

This is Phase-1 work: no real Samsung Health SDK, no Android app. The fixture schema is forward-compatible with the Phase-2 real watch stream so agent contracts need zero changes when the real watch is added.

---

## 2. Scope

### In scope
- `vitals_reading` + `vitals_anomaly` Postgres tables (migration 002)
- `POST /api/vitals` ingest endpoint
- `VitalsSubAgent` — Haiku 4.5, anomaly classification, safety-gatekeeper-wrapped narratives
- `app/workers/vitals.py` — polling orchestrator (30-second poll)
- `GET /vitals-simulator` — web UI with five scenario buttons
- `app/wearable/fixture.py` — five named scenario payloads
- Memory injection: `/memories/{senior_id}/vitals_flags.json`
- Telegram URGENT/HIGH alert via existing bot alert path
- Daily brief integration: vitals anomalies included in brief narrative
- `.claude/agents/vitals-subagent.md` agent contract
- Unit + smoke tests

### Out of scope (Phase 2)
- Samsung Health Data SDK / Health Connect
- Android / Wear OS companion app
- Skin temperature baseline computation
- Sleep quality classification
- Real-time WebSocket stream

---

## 3. Architecture

```
Simulator Web UI  GET /vitals-simulator
        │
        │  POST /api/vitals  (JSON body)
        ▼
app/api/vitals.py  ──────────────────────► vitals_reading (Postgres)
                                                    │
                              app/workers/vitals.py (polls every 30s)
                                    │ calls
                              app/agents/vitals.py  (VitalsSubAgent)
                              Model: Haiku 4.5
                              Input: VitalsReading + 7-day baseline
                              Output: List[VitalsAnomalyResult]
                              safety-gatekeeper wraps every narrative
                                                    │
                         ┌──────────┬───────────────┘
                         ▼          ▼              ▼
              Telegram URGENT   memory write    vitals_anomaly row
              alert to Priya    /memories/      → daily brief worker
                (app/bot)       {senior_id}/    (app/workers/brief.py)
                                vitals_flags.json
```

---

## 4. Data Model

### 4.1 `vitals_reading`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `senior_id` | UUID FK → `senior` | |
| `source` | TEXT | `'simulator' \| 'samsung_health' \| 'fixture'` |
| `recorded_at` | TIMESTAMPTZ | from payload; defaults to `now()` |
| `hr_bpm` | NUMERIC nullable | |
| `spo2_pct` | NUMERIC nullable | |
| `step_count` | INTEGER nullable | daily cumulative |
| `skin_temp_delta` | NUMERIC nullable | stub — Phase 2 |
| `sleep_hours` | NUMERIC nullable | stub — Phase 2 |
| `raw_payload` | JSONB | full payload for forward-compat |
| `processed` | BOOLEAN DEFAULT false | worker sets true after processing |
| `created_at` | TIMESTAMPTZ DEFAULT now() | |

Index: `(senior_id, processed)` — worker query.

### 4.2 `vitals_anomaly`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `senior_id` | UUID FK → `senior` | |
| `reading_id` | UUID FK → `vitals_reading` | |
| `marker` | TEXT | `'hr' \| 'spo2' \| 'step_count' \| 'skin_temp' \| 'sleep'` |
| `severity` | TEXT | `'MEDIUM' \| 'HIGH' \| 'URGENT'` |
| `value` | NUMERIC | observed reading |
| `threshold` | NUMERIC | threshold that was breached |
| `narrative` | TEXT | safety-gatekeeper-approved string |
| `alerted_at` | TIMESTAMPTZ nullable | set when Telegram alert fired |
| `briefed` | BOOLEAN DEFAULT false | set when included in daily brief |
| `created_at` | TIMESTAMPTZ DEFAULT now() | |

### 4.3 Anomaly Thresholds

| Marker | MEDIUM | HIGH | URGENT |
|--------|--------|------|--------|
| HR (bpm) | >95 or <50 | >105 or <45 | >120 or <40 |
| SpO2 (%) | <95 | <93 | <90 |
| Step count (daily) | <2,000 | — | — |
| Skin temp delta (°C) | >0.5 | — | — (stub) |
| Sleep hours | <5 | — | — (stub) |

Only HR and SpO2 produce HIGH/URGENT alerts to Telegram. Step count produces MEDIUM only (included in brief, not immediate alert).

---

## 5. New Modules

### 5.1 `app/api/vitals.py`
FastAPI router. Two endpoints:

```
POST /api/vitals
Body: { senior_id, source, recorded_at?, hr_bpm?, spo2_pct?, step_count?,
        skin_temp_delta?, sleep_hours?, raw_payload? }
Response 201: { reading_id }
```
Validates `senior_id` exists. Writes `vitals_reading` row with `processed=false`.

```
GET /api/vitals/status/{senior_id}
Response 200: {
  last_reading: { hr_bpm, spo2_pct, step_count, recorded_at, source } | null,
  recent_anomalies: [
    { marker, severity, value, threshold, narrative, created_at }
  ]  -- last 5 anomalies, ordered by created_at DESC
}
```
Used by simulator status panel (polled every 5 seconds). Returns latest unprocessed
or most-recently-processed reading for the senior, plus up to 5 recent anomaly rows.

### 5.2 `app/agents/vitals.py` — VitalsSubAgent
- Model: `claude-haiku-4-5-20251001`, thinking off
- Input: one `VitalsReading` ORM object + `VitalsBaseline` (7-day avg HR, SpO2, step_count)
- Output: `list[VitalsAnomalyResult]` — each has `(marker, severity, value, threshold, narrative)`
- Returns `[]` if all readings within normal range
- Metadata: `{"agent": "VitalsSubAgent", "senior_id": str(senior_id)}`
- Safety-gatekeeper is called **inside** `VitalsSubAgent.run()` on each narrative string
  before it is included in any `VitalsAnomalyResult`. The worker never calls the gatekeeper
  separately — it trusts that any narrative it receives from the agent is already approved.

`VitalsBaseline` for Phase 1: hardcoded per-persona constants in `app/wearable/fixture.py`
(Lakshmi: hr_avg=74, spo2_avg=97, step_avg=5200).

### 5.3 `app/workers/vitals.py`
Async polling worker. Loop:
1. Query `vitals_reading WHERE processed=false ORDER BY recorded_at LIMIT 50`
2. For each reading: load baseline → call `VitalsSubAgent` → write `vitals_anomaly` rows
3. For each URGENT/HIGH anomaly: fire Telegram alert to Priya
4. Write/merge `/memories/{senior_id}/vitals_flags.json`
5. Mark reading `processed=true`
6. Sleep 30 seconds

### 5.4 `app/wearable/fixture.py`

`VitalsPayload` is a `dataclasses.dataclass` (or `pydantic.BaseModel`):
```python
@dataclass
class VitalsPayload:
    hr_bpm: float | None = None
    spo2_pct: float | None = None
    step_count: int | None = None
    skin_temp_delta: float | None = None
    sleep_hours: float | None = None
    source: str = "fixture"

@dataclass
class VitalsBaseline:
    hr_avg: float
    spo2_avg: float
    step_avg: float

LAKSHMI_BASELINE = VitalsBaseline(hr_avg=74, spo2_avg=97, step_avg=5200)

BASELINES: dict[str, VitalsBaseline] = {
    "lakshmi": LAKSHMI_BASELINE,
}

SCENARIOS: dict[str, VitalsPayload] = {
    "normal":            VitalsPayload(hr_bpm=72,  spo2_pct=98, step_count=6500),
    "post_med_hr_spike": VitalsPayload(hr_bpm=108, spo2_pct=96, step_count=4200),
    "spo2_dip":          VitalsPayload(hr_bpm=78,  spo2_pct=91, step_count=3100),
    "low_step_fatigue":  VitalsPayload(hr_bpm=74,  spo2_pct=97, step_count=1800),
    "dizziness_episode": VitalsPayload(hr_bpm=112, spo2_pct=88, step_count=1600),
}
```
`dizziness_episode` SpO2 is set to 88% (URGENT threshold <90) to match the
intended URGENT severity. Maps to Lakshmi's Apr 4/11/18 clinical pattern (PRD §6.7).

### 5.5 Simulator Web UI (`app/templates/vitals_simulator.html`)
Static Jinja2 template served at `GET /vitals-simulator`. No JS framework.
- Senior selector (defaults to Lakshmi Iyer UUID)
- Five scenario buttons, each POSTs to `/api/vitals`
- Status panel: shows last posted reading + last anomaly detected (polls `GET /api/vitals/status/{senior_id}` every 5 seconds)

---

## 6. Integration Points

### 6.1 Telegram alert
Reuses existing bot alert path in `app/bot/`. Worker calls the same send function
used for lab URGENT flags. Message format:
```
⚠️ URGENT — Vitals anomaly detected for Lakshmi Iyer
SpO₂: 88% (threshold: <90%)
Heart rate: 112 bpm (threshold: >105 bpm)
Consider checking in. [informational summary, physician review recommended]
```
All strings are safety-gatekeeper-approved before insertion.

### 6.2 Memory injection
Worker writes/merges `/memories/{senior_id}/vitals_flags.json`:
```json
{
  "last_updated": "2026-04-23T14:32:00Z",
  "recent_anomalies": [
    { "marker": "spo2", "severity": "URGENT", "value": 91,
      "recorded_at": "2026-04-23T14:31:00Z", "narrative": "..." }
  ]
}
```
SymptomSubAgent and ReportAgent already read memory files — vitals flags appear
in Doctor Visit Report automatically with no code changes to those agents.

### 6.3 Daily brief
**Note:** `app/workers/brief.py` is currently a Day-4 stub (`{"status": "pending_day4_implementation"}`).
The vitals brief integration is a **co-implementation** — it must be built as part of the Day-4
brief worker, not as an edit to existing logic. The `briefed` column on `vitals_anomaly` is
reserved now so the Day-4 implementer can query `WHERE briefed=false AND senior_id=X` and mark
`briefed=true` after the brief is sent. No Day-3 code changes needed to `brief.py`.

---

## 7. Agent Contract

File: `.claude/agents/vitals-subagent.md`

```
purpose: Classify vitals readings against thresholds and produce
         safety-gatekeeper-approved anomaly narratives.
model:   claude-haiku-4-5-20251001
effort:  n/a (thinking off)
input:   VitalsReading + VitalsBaseline
output:  List[VitalsAnomalyResult]
system:  You are a vitals anomaly classifier for an Indian eldercare
         health companion. Given a single vitals reading and the
         senior's 7-day baseline, return a structured list of
         anomalies. Use only metric values and clinical threshold
         language — never diagnose, never use 'abnormal', never
         name a disease or specify a dosage change.
```

---

## 8. Testing

### 8.1 `tests/test_vitals_smoke.py`
- POST each of the 5 scenarios to `/api/vitals` for Lakshmi
- Trigger worker manually (or await poll cycle)
- Assert `vitals_anomaly` rows exist with correct `marker` + `severity`
- Assert Telegram mock called for `dizziness_episode` — HR produces HIGH (>105), SpO2 produces URGENT (<90)
- Assert `processed=true` on reading after worker runs

### 8.2 `tests/test_vitals_agent.py`
- Unit test `VitalsSubAgent` directly with fixture payloads
- No DB, no HTTP — pure agent input/output
- Assert `dizziness_episode` produces ≥2 anomalies with severity HIGH or URGENT
- Assert `normal` produces empty list

### 8.3 `migrations/versions/002_vitals.py`
- Alembic migration: create `vitals_reading` + `vitals_anomaly` tables
- Existing smoke tests must still pass after migration

---

## 9. Files Changed / Created

| File | Action |
|------|--------|
| `migrations/versions/002_vitals.py` | Create |
| `app/db/models.py` | Edit — add `VitalsReading`, `VitalsAnomaly` ORM models |
| `app/api/vitals.py` | Create |
| `app/agents/vitals.py` | Create |
| `app/workers/vitals.py` | Create |
| `app/wearable/__init__.py` | Create |
| `app/wearable/fixture.py` | Create |
| `app/templates/vitals_simulator.html` | Create |
| `app/main.py` | Edit — mount vitals router + simulator route |
| `app/workers/brief.py` | Day-4 co-implementation — add vitals anomaly query when brief worker is built |
| `.claude/agents/vitals-subagent.md` | Create |
| `tests/test_vitals_smoke.py` | Create |
| `tests/test_vitals_agent.py` | Create |

---

## 10. LLM model compliance

Follows CLAUDE.md non-negotiable rules:
- VitalsSubAgent: Haiku 4.5 (hot path, latency-critical)
- No Opus on the ingest/classification path
- All metadata includes `{"agent": "VitalsSubAgent", "senior_id": ...}`
- No `extended-thinking` headers
- Safety-gatekeeper wraps every narrative before DB write

---

## 11. Demo script (2 minutes)

1. Open `http://localhost:8080/vitals-simulator`
2. Click **"Dizziness episode"** — maps to Lakshmi's Apr 4/11/18 pattern
3. Status panel shows: `hr=112 bpm · SpO₂=88% · steps=1,600`
4. Within 30 seconds: Priya receives Telegram URGENT alert
5. Show `/memories/lakshmi-uuid/vitals_flags.json` — anomaly is persisted
6. Trigger daily brief — anomaly appears in brief narrative to Priya
7. Open Doctor Visit Report — vitals flags section populated automatically
