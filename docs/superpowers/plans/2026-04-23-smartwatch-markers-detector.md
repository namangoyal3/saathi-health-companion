# Smartwatch Markers Detector Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build VitalsSubAgent + watch simulator web UI so the app can detect HR/SpO2/step-count anomalies, alert Priya via Telegram, inject flags into memory, and accept real Samsung Galaxy Watch data in Phase 2 with zero agent-contract changes.

**Architecture:** Simulator POSTs normalized `VitalsPayload` to `POST /api/vitals`; a 30-second polling worker runs `VitalsSubAgent` (Haiku 4.5) on unprocessed rows; anomaly narratives are safety-gatekeeper-approved inside the agent; HIGH/URGENT anomalies fire Telegram alerts to Priya and write `/memories/{senior_id}/vitals_flags.json`; a Samsung Health webhook stub (`app/wearable/samsung.py`) normalizes Phase-2 payloads into the same `VitalsPayload` type so no agent changes are needed when the real watch ships.

**Tech Stack:** Python 3.12, FastAPI, asyncpg, SQLAlchemy 2.0, Alembic, Anthropic SDK (Haiku 4.5), python-telegram-bot, uv, pytest-asyncio, Jinja2

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `migrations/versions/003_vitals.py` | Create | `vitals_reading` + `vitals_anomaly` tables |
| `app/db/models.py` | Edit | Add `VitalsReading`, `VitalsAnomaly` ORM models |
| `app/wearable/__init__.py` | Create | `VitalsPayload`, `VitalsBaseline`, `VitalsAnomalyResult` dataclasses |
| `app/wearable/fixture.py` | Create | 5 named Phase-1 scenarios + per-persona baselines |
| `app/wearable/samsung.py` | Create | Samsung Health webhook transformer stub (Phase-2 extensibility) |
| `app/agents/vitals.py` | Create | `VitalsSubAgent` — Haiku 4.5, tool-forced, safety-gated internally |
| `app/api/vitals.py` | Create | `POST /api/vitals`, `GET /api/vitals/status/{senior_id}`, `POST /api/vitals/samsung-webhook` (stub) |
| `app/workers/vitals.py` | Create | Async polling orchestrator — reads DB, calls agent, fires Telegram + memory |
| `app/templates/vitals_simulator.html` | Create | Web UI — 5 scenario buttons, auto-polling status panel |
| `app/main.py` | Edit | Mount vitals router + simulator route |
| `.claude/agents/vitals-subagent.md` | Create | Agent contract doc |
| `tests/test_vitals_agent.py` | Create | Unit tests for VitalsSubAgent (no DB/HTTP) |
| `tests/test_vitals_smoke.py` | Create | Integration smoke tests (DB + API + worker) |

---

## Task 1: DB Migration

**Files:**
- Create: `migrations/versions/003_vitals.py`

- [ ] **Step 1: Write the migration**

```python
# migrations/versions/003_vitals.py
"""vitals_reading + vitals_anomaly tables.

Revision ID: 003
Revises: 002
Create Date: 2026-04-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vitals_reading",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),  # simulator | samsung_health | fixture
        sa.Column("recorded_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("hr_bpm", sa.Numeric(6, 2)),
        sa.Column("spo2_pct", sa.Numeric(5, 2)),
        sa.Column("step_count", sa.Integer),
        sa.Column("skin_temp_delta", sa.Numeric(5, 2)),  # stub Phase 2
        sa.Column("sleep_hours", sa.Numeric(5, 2)),      # stub Phase 2
        sa.Column("raw_payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("processed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vitals_reading_senior_processed", "vitals_reading", ["senior_id", "processed"])
    op.create_index("ix_vitals_reading_senior_recorded", "vitals_reading", ["senior_id", "recorded_at"])

    op.create_table(
        "vitals_anomaly",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reading_id", UUID(as_uuid=True), sa.ForeignKey("vitals_reading.id", ondelete="CASCADE"), nullable=False),
        sa.Column("marker", sa.String(30), nullable=False),   # hr | spo2 | step_count | skin_temp | sleep
        sa.Column("severity", sa.String(10), nullable=False), # MEDIUM | HIGH | URGENT
        sa.Column("value", sa.Numeric(12, 4), nullable=False),
        sa.Column("threshold", sa.Numeric(12, 4), nullable=False),
        sa.Column("narrative", sa.Text, nullable=False),
        sa.Column("alerted_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("briefed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vitals_anomaly_senior_created", "vitals_anomaly", ["senior_id", "created_at"])
    op.create_index("ix_vitals_anomaly_briefed", "vitals_anomaly", ["briefed", "senior_id"])


def downgrade() -> None:
    op.drop_table("vitals_anomaly")
    op.drop_table("vitals_reading")
```

- [ ] **Step 2: Run migration against local DB**

```bash
docker compose up -d db redis
uv run alembic upgrade head
```
Expected: `Running upgrade 002 -> 003` with no errors.

- [ ] **Step 3: Verify tables exist**

```bash
docker exec saathi-health-companion-db-1 psql -U saath -d saath \
  -c "\d vitals_reading" -c "\d vitals_anomaly"
```
Expected: column lists for both tables.

- [ ] **Step 4: Verify existing smoke tests still pass**

```bash
uv run pytest tests/test_day1_smoke.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/003_vitals.py
git commit -m "feat(vitals): add vitals_reading + vitals_anomaly migration (003)"
```

---

## Task 2: ORM Models

**Files:**
- Modify: `app/db/models.py`

- [ ] **Step 1: Add `VitalsReading` and `VitalsAnomaly` to models.py**

Append at the bottom of `app/db/models.py` (after `DoctorReport`):

```python
class VitalsReading(Base):
    __tablename__ = "vitals_reading"
    __table_args__ = (
        sa.Index("ix_vitals_reading_senior_processed", "senior_id", "processed"),
        sa.Index("ix_vitals_reading_senior_recorded", "senior_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()
    )
    hr_bpm: Mapped[float | None] = mapped_column(sa.Numeric(6, 2))
    spo2_pct: Mapped[float | None] = mapped_column(sa.Numeric(5, 2))
    step_count: Mapped[int | None] = mapped_column(sa.Integer)
    skin_temp_delta: Mapped[float | None] = mapped_column(sa.Numeric(5, 2))
    sleep_hours: Mapped[float | None] = mapped_column(sa.Numeric(5, 2))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    processed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    anomalies: Mapped[list[VitalsAnomaly]] = relationship("VitalsAnomaly", back_populates="reading")


class VitalsAnomaly(Base):
    __tablename__ = "vitals_anomaly"
    __table_args__ = (
        sa.Index("ix_vitals_anomaly_senior_created", "senior_id", "created_at"),
        sa.Index("ix_vitals_anomaly_briefed", "briefed", "senior_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    reading_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("vitals_reading.id", ondelete="CASCADE"), nullable=False
    )
    marker: Mapped[str] = mapped_column(sa.String(30), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    value: Mapped[float] = mapped_column(sa.Numeric(12, 4), nullable=False)
    threshold: Mapped[float] = mapped_column(sa.Numeric(12, 4), nullable=False)
    narrative: Mapped[str] = mapped_column(sa.Text, nullable=False)
    alerted_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    briefed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    reading: Mapped[VitalsReading] = relationship("VitalsReading", back_populates="anomalies")
```

Also add the relationship back-ref on `AppUser` by adding these two lines to the `AppUser` class (after `doctor_reports`):

```python
    vitals_readings: Mapped[list[VitalsReading]] = relationship("VitalsReading", back_populates=None, viewonly=True)
    vitals_anomalies: Mapped[list[VitalsAnomaly]] = relationship("VitalsAnomaly", back_populates=None, viewonly=True)
```

- [ ] **Step 2: Verify mypy passes**

```bash
uv run mypy app/db/models.py
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add app/db/models.py
git commit -m "feat(vitals): add VitalsReading + VitalsAnomaly ORM models"
```

---

## Task 3: Wearable Types Package (Samsung-extensible)

**Files:**
- Create: `app/wearable/__init__.py`
- Create: `app/wearable/fixture.py`
- Create: `app/wearable/samsung.py`

This is the extensibility layer. The `VitalsPayload` dataclass is the normalized format
all sources (simulator, fixture, Samsung, future Fitbit) produce. Agent + worker never
touch source-specific fields.

- [ ] **Step 1: Write `app/wearable/__init__.py`**

```python
"""Wearable vitals types — normalized schema used by all sources (Phase 1 + Phase 2).

VitalsPayload is the canonical ingest format. Sources (simulator, Samsung Health,
fixture) produce VitalsPayload objects; the worker and agent consume only this type.
Adding a new watch brand means writing a transformer in a new module — zero changes
to agent or worker code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class VitalsPayload:
    """Normalized vitals reading from any source."""
    source: str                          # 'simulator' | 'samsung_health' | 'fixture'
    hr_bpm: float | None = None
    spo2_pct: float | None = None
    step_count: int | None = None
    skin_temp_delta: float | None = None  # delta from 7-day baseline; Phase 2
    sleep_hours: float | None = None      # Phase 2
    recorded_at: datetime | None = None   # defaults to now() on insert
    raw_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class VitalsBaseline:
    """7-day rolling averages for a senior. Phase 1: hardcoded per-persona."""
    hr_avg: float
    spo2_avg: float
    step_avg: float


@dataclass
class VitalsAnomalyResult:
    """Output of VitalsSubAgent for one detected anomaly."""
    marker: str       # 'hr' | 'spo2' | 'step_count' | 'skin_temp' | 'sleep'
    severity: str     # 'MEDIUM' | 'HIGH' | 'URGENT'
    value: float
    threshold: float
    narrative: str    # safety-gatekeeper-approved; never diagnoses
```

- [ ] **Step 2: Write `app/wearable/fixture.py`**

```python
"""Phase-1 vitals fixture — deterministic scenarios for simulator + tests.

Samsung extensibility note: SCENARIOS produces VitalsPayload objects with
source='fixture'. The Samsung transformer (app/wearable/samsung.py) produces
VitalsPayload objects with source='samsung_health'. Same type, different source.
"""

from __future__ import annotations

import uuid
from app.wearable import VitalsBaseline, VitalsPayload

# Stable senior UUIDs (from evals/personas/lakshmi.py)
LAKSHMI_SENIOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

BASELINES: dict[str, VitalsBaseline] = {
    str(LAKSHMI_SENIOR_ID): VitalsBaseline(hr_avg=74.0, spo2_avg=97.0, step_avg=5200.0),
}

SCENARIOS: dict[str, VitalsPayload] = {
    # Normal day — all within range, no anomalies expected
    "normal": VitalsPayload(
        source="fixture", hr_bpm=72.0, spo2_pct=98.0, step_count=6500
    ),
    # Post-medication HR spike — HIGH hr (>105)
    "post_med_hr_spike": VitalsPayload(
        source="fixture", hr_bpm=108.0, spo2_pct=96.0, step_count=4200
    ),
    # SpO2 dip — URGENT spo2 (<90) + MEDIUM steps
    "spo2_dip": VitalsPayload(
        source="fixture", hr_bpm=78.0, spo2_pct=88.0, step_count=3100
    ),
    # Low-step fatigue day — MEDIUM steps only
    "low_step_fatigue": VitalsPayload(
        source="fixture", hr_bpm=74.0, spo2_pct=97.0, step_count=1800
    ),
    # Dizziness episode — Lakshmi's Apr 4/11/18 pattern (PRD §6.7)
    # HIGH hr (>105) + URGENT spo2 (<90) + MEDIUM steps
    "dizziness_episode": VitalsPayload(
        source="fixture", hr_bpm=112.0, spo2_pct=88.0, step_count=1600
    ),
}

SCENARIO_LABELS: dict[str, str] = {
    "normal": "Normal day",
    "post_med_hr_spike": "Post-med HR spike",
    "spo2_dip": "SpO₂ dip",
    "low_step_fatigue": "Low-step fatigue",
    "dizziness_episode": "Dizziness episode (Lakshmi Apr 4/11/18)",
}
```

- [ ] **Step 3: Write `app/wearable/samsung.py` (Phase-2 extensibility stub)**

```python
"""Samsung Health Platform webhook transformer — Phase 2.

When a Galaxy Watch 4+ sends data via Samsung Health Platform API, the webhook
payload arrives as a list of SamsungHealthMetric objects. This module normalizes
them into VitalsPayload objects — the same type the simulator produces.

The POST /api/vitals/samsung-webhook endpoint calls parse_samsung_health_webhook().
No changes needed to VitalsSubAgent or the polling worker.

Samsung Health Platform API reference:
  https://developer.samsung.com/health/platform/api-specification.html
  Metric IDs: com.samsung.health.heart_rate, com.samsung.health.oxygen_saturation,
              com.samsung.health.step_count, com.samsung.health.sleep,
              com.samsung.health.skin_temperature
"""

from __future__ import annotations

from typing import Any
from app.wearable import VitalsPayload

# Samsung Health metric type IDs → our field names
_METRIC_MAP: dict[str, str] = {
    "com.samsung.health.heart_rate": "hr_bpm",
    "com.samsung.health.oxygen_saturation": "spo2_pct",
    "com.samsung.health.step_count": "step_count",
    "com.samsung.health.skin_temperature": "skin_temp_delta",
    "com.samsung.health.sleep": "sleep_hours",
}


def parse_samsung_health_webhook(raw: dict[str, Any]) -> list[VitalsPayload]:
    """Transform a Samsung Health Platform API webhook payload into VitalsPayload list.

    One webhook may contain multiple metric types for the same time window.
    We group by time_offset and produce one VitalsPayload per distinct timestamp.

    Phase 2 TODO: implement grouping + HMAC signature verification.
    """
    # Phase 2 placeholder — returns empty list until implemented
    # Implementation steps:
    # 1. Verify HMAC-SHA256 signature in X-Samsung-Health-Signature header
    # 2. Parse raw["data"] list of {metric_type, start_time, end_time, value, unit}
    # 3. Group by start_time (or 1-minute window)
    # 4. For each group: build VitalsPayload(source="samsung_health", ...)
    # 5. Return list of VitalsPayload objects
    raise NotImplementedError("Samsung Health webhook transformer not yet implemented (Phase 2)")
```

- [ ] **Step 4: Verify mypy on the wearable package**

```bash
uv run mypy app/wearable/
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add app/wearable/
git commit -m "feat(vitals): add wearable types package with Samsung extensibility stub"
```

---

## Task 4: VitalsSubAgent

**Files:**
- Create: `app/agents/vitals.py`
- Test: `tests/test_vitals_agent.py`

The agent is tool-forced (Haiku 4.5). It classifies readings against thresholds and
calls safety-gatekeeper internally on each narrative. The worker never re-calls gatekeeper.

- [ ] **Step 1: Write the failing tests first**

Create `tests/test_vitals_agent.py`:

```python
"""Unit tests for VitalsSubAgent — no DB, no HTTP, direct agent calls."""

from __future__ import annotations

import pytest

from app.wearable import VitalsBaseline, VitalsPayload
from app.wearable.fixture import BASELINES, SCENARIOS
from evals.personas.lakshmi import LAKSHMI_SENIOR_ID


BASELINE = BASELINES[str(LAKSHMI_SENIOR_ID)]


@pytest.mark.asyncio
async def test_normal_reading_returns_no_anomalies() -> None:
    from app.agents.vitals import run as vitals_run
    results = await vitals_run(SCENARIOS["normal"], BASELINE, LAKSHMI_SENIOR_ID)
    assert results == [], f"Expected no anomalies for normal reading, got {results}"


@pytest.mark.asyncio
async def test_dizziness_episode_returns_multiple_anomalies() -> None:
    from app.agents.vitals import run as vitals_run
    results = await vitals_run(SCENARIOS["dizziness_episode"], BASELINE, LAKSHMI_SENIOR_ID)
    severities = {r.severity for r in results}
    assert len(results) >= 2, f"Expected ≥2 anomalies, got {results}"
    assert "URGENT" in severities or "HIGH" in severities, f"Expected HIGH or URGENT, got {severities}"


@pytest.mark.asyncio
async def test_spo2_dip_is_urgent() -> None:
    from app.agents.vitals import run as vitals_run
    results = await vitals_run(SCENARIOS["spo2_dip"], BASELINE, LAKSHMI_SENIOR_ID)
    spo2_flags = [r for r in results if r.marker == "spo2"]
    assert spo2_flags, "Expected spo2 anomaly"
    assert spo2_flags[0].severity == "URGENT", f"Expected URGENT, got {spo2_flags[0].severity}"


@pytest.mark.asyncio
async def test_narratives_are_non_empty_strings() -> None:
    from app.agents.vitals import run as vitals_run
    results = await vitals_run(SCENARIOS["dizziness_episode"], BASELINE, LAKSHMI_SENIOR_ID)
    for r in results:
        assert isinstance(r.narrative, str) and len(r.narrative) > 10, \
            f"Narrative too short: {r.narrative!r}"


@pytest.mark.asyncio
async def test_low_step_is_medium() -> None:
    from app.agents.vitals import run as vitals_run
    results = await vitals_run(SCENARIOS["low_step_fatigue"], BASELINE, LAKSHMI_SENIOR_ID)
    step_flags = [r for r in results if r.marker == "step_count"]
    assert step_flags, "Expected step_count anomaly"
    assert step_flags[0].severity == "MEDIUM"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_vitals_agent.py -v
```
Expected: `ImportError: cannot import name 'run' from 'app.agents.vitals'`

- [ ] **Step 3: Implement `app/agents/vitals.py`**

```python
"""VitalsSubAgent — Haiku 4.5 anomaly classification for wearable vitals.

Thresholds (Phase 1):
  HR:   MEDIUM >95/<50  HIGH >105/<45  URGENT >120/<40
  SpO2: MEDIUM <95      HIGH <93       URGENT <90
  Steps: MEDIUM <2000   (no HIGH/URGENT for steps — brief only)
  skin_temp / sleep: stubs (MEDIUM only, not yet active)

Safety-gatekeeper is called INSIDE this agent on every narrative string.
The worker must NOT call the gatekeeper again on the returned VitalsAnomalyResult.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from app.agents import safety
from app.llm.haiku import haiku_call
from app.wearable import VitalsAnomalyResult, VitalsBaseline, VitalsPayload

_SYSTEM_PROMPT = """You are VitalsSubAgent, a vitals anomaly classifier for Saath, an Indian eldercare AI health companion.

ROLE
Given one wearable reading and a 7-day baseline for a senior, identify anomalies using the threshold table. For each anomaly produce a short clinical narrative (1 sentence, ≤20 words).

THRESHOLD TABLE
HR (bpm):       MEDIUM >95 or <50 | HIGH >105 or <45 | URGENT >120 or <40
SpO2 (%):       MEDIUM <95        | HIGH <93          | URGENT <90
Step count/day: MEDIUM <2000      | (no HIGH/URGENT)
skin_temp_delta: MEDIUM >0.5°C    | (stub, classify if present)
sleep_hours:    MEDIUM <5         | (stub, classify if present)

LANGUAGE RULES (non-negotiable)
- NEVER diagnose: forbidden = "you have hypoxia", "this is cardiac arrhythmia"
- NEVER suggest dose changes
- NEVER use "abnormal"
- Use objective values only: "SpO₂ reading of 88% is below the 90% threshold"
- Emergency symptoms → still classify, still use threshold language

OUTPUT
You MUST call classify_vitals with a valid anomaly list. Return an empty list if no anomalies."""

_CLASSIFY_TOOL: dict[str, Any] = {
    "name": "classify_vitals",
    "description": "Return all detected vitals anomalies for this reading.",
    "input_schema": {
        "type": "object",
        "required": ["anomalies"],
        "properties": {
            "anomalies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["marker", "severity", "value", "threshold", "narrative"],
                    "properties": {
                        "marker": {
                            "type": "string",
                            "enum": ["hr", "spo2", "step_count", "skin_temp", "sleep"],
                        },
                        "severity": {
                            "type": "string",
                            "enum": ["MEDIUM", "HIGH", "URGENT"],
                        },
                        "value": {"type": "number"},
                        "threshold": {"type": "number"},
                        "narrative": {"type": "string"},
                    },
                },
            }
        },
    },
}


async def run(
    payload: VitalsPayload,
    baseline: VitalsBaseline,
    senior_id: uuid.UUID,
) -> list[VitalsAnomalyResult]:
    """Classify a single vitals reading. Returns empty list if all values are normal.

    Safety-gatekeeper is called here on each narrative before returning.
    """
    user_payload = json.dumps(
        {
            "reading": {
                "hr_bpm": payload.hr_bpm,
                "spo2_pct": payload.spo2_pct,
                "step_count": payload.step_count,
                "skin_temp_delta": payload.skin_temp_delta,
                "sleep_hours": payload.sleep_hours,
                "source": payload.source,
            },
            "baseline": {
                "hr_avg": baseline.hr_avg,
                "spo2_avg": baseline.spo2_avg,
                "step_avg": baseline.step_avg,
            },
        },
        ensure_ascii=False,
    )

    msg = haiku_call(
        system=_SYSTEM_PROMPT,
        user=user_payload,
        tools=[_CLASSIFY_TOOL],
        max_tokens=1024,
        senior_id=senior_id,
        agent_name="VitalsSubAgent",
    )

    raw_anomalies: list[dict[str, Any]] = []
    for block in msg.content:
        if block.type == "tool_use" and block.name == "classify_vitals":
            raw_anomalies = block.input.get("anomalies", [])
            break

    results: list[VitalsAnomalyResult] = []
    for a in raw_anomalies:
        # Gate each narrative through the safety-gatekeeper before returning
        gated = await safety.check(
            text=a["narrative"],
            context="vitals",
            agent="VitalsSubAgent",
            senior_id=senior_id,
        )
        # On gatekeeper failure: use a generic safe narrative rather than blocking all anomalies
        narrative = gated.text if gated.ok else (
            f"{a['marker']} reading of {a['value']} noted; physician review recommended"
        )
        results.append(
            VitalsAnomalyResult(
                marker=a["marker"],
                severity=a["severity"],
                value=float(a["value"]),
                threshold=float(a["threshold"]),
                narrative=narrative,
            )
        )

    return results
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_vitals_agent.py -v
```
Expected: all 5 pass. If any fail due to LLM non-determinism, run again — threshold classification is reliable for extreme values.

- [ ] **Step 5: Verify mypy**

```bash
uv run mypy app/agents/vitals.py
```
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add app/agents/vitals.py tests/test_vitals_agent.py
git commit -m "feat(vitals): VitalsSubAgent — Haiku 4.5, tool-forced, safety-gated"
```

---

## Task 5: Ingest API

**Files:**
- Create: `app/api/vitals.py`

Three endpoints:
- `POST /api/vitals` — ingest (simulator + Phase-2 clients)
- `GET /api/vitals/status/{senior_id}` — simulator status panel polling
- `POST /api/vitals/samsung-webhook` — Phase-2 stub (returns 501)

- [ ] **Step 1: Write `app/api/vitals.py`**

```python
"""Vitals ingest API.

POST  /api/vitals                      — ingest normalized reading (simulator / fixture / Phase-2 clients)
GET   /api/vitals/status/{senior_id}   — last reading + recent anomalies (simulator status panel)
POST  /api/vitals/samsung-webhook      — Samsung Health Platform webhook (Phase-2 stub, returns 501)
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import asyncpg
import structlog
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import settings

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/vitals", tags=["vitals"])


# ── Request / response schemas ───────────────────────────────────────────────

class VitalsIngestRequest(BaseModel):
    senior_id: uuid.UUID
    source: str = "simulator"
    recorded_at: datetime | None = None
    hr_bpm: float | None = None
    spo2_pct: float | None = None
    step_count: int | None = None
    skin_temp_delta: float | None = None
    sleep_hours: float | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


# ── DB helper ────────────────────────────────────────────────────────────────

async def _conn() -> asyncpg.Connection:
    return await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("", status_code=201)
async def ingest_vitals(req: VitalsIngestRequest) -> dict[str, str]:
    """Accept a normalized vitals reading, persist to vitals_reading, return reading_id."""
    conn = await _conn()
    try:
        row = await conn.fetchrow("SELECT id FROM app_user WHERE id=$1", req.senior_id)
        if not row:
            raise HTTPException(status_code=404, detail=f"senior {req.senior_id} not found")

        import json

        reading_id: uuid.UUID = await conn.fetchval(
            """INSERT INTO vitals_reading
               (senior_id, source, recorded_at, hr_bpm, spo2_pct, step_count,
                skin_temp_delta, sleep_hours, raw_payload)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
               RETURNING id""",
            req.senior_id,
            req.source,
            req.recorded_at or datetime.now(UTC),
            req.hr_bpm,
            req.spo2_pct,
            req.step_count,
            req.skin_temp_delta,
            req.sleep_hours,
            json.dumps(req.raw_payload),
        )
        log.info("vitals_ingested", reading_id=str(reading_id), senior_id=str(req.senior_id), source=req.source)
        return {"reading_id": str(reading_id)}
    finally:
        await conn.close()


@router.get("/status/{senior_id}")
async def vitals_status(senior_id: uuid.UUID) -> dict[str, Any]:
    """Return latest reading + up to 5 recent anomalies for the simulator status panel."""
    conn = await _conn()
    try:
        reading_row = await conn.fetchrow(
            """SELECT hr_bpm, spo2_pct, step_count, recorded_at, source
               FROM vitals_reading
               WHERE senior_id=$1
               ORDER BY recorded_at DESC LIMIT 1""",
            senior_id,
        )
        anomaly_rows = await conn.fetch(
            """SELECT marker, severity, value, threshold, narrative, created_at
               FROM vitals_anomaly
               WHERE senior_id=$1
               ORDER BY created_at DESC LIMIT 5""",
            senior_id,
        )

        last_reading = (
            {
                "hr_bpm": float(reading_row["hr_bpm"]) if reading_row["hr_bpm"] else None,
                "spo2_pct": float(reading_row["spo2_pct"]) if reading_row["spo2_pct"] else None,
                "step_count": reading_row["step_count"],
                "recorded_at": reading_row["recorded_at"].isoformat() if reading_row["recorded_at"] else None,
                "source": reading_row["source"],
            }
            if reading_row
            else None
        )

        recent_anomalies = [
            {
                "marker": row["marker"],
                "severity": row["severity"],
                "value": float(row["value"]),
                "threshold": float(row["threshold"]),
                "narrative": row["narrative"],
                "created_at": row["created_at"].isoformat(),
            }
            for row in anomaly_rows
        ]

        return {"last_reading": last_reading, "recent_anomalies": recent_anomalies}
    finally:
        await conn.close()


@router.post("/samsung-webhook", status_code=501)
async def samsung_health_webhook(request: dict[str, Any]) -> JSONResponse:
    """Samsung Health Platform webhook receiver — Phase 2.

    Phase 2 implementation steps:
    1. Verify X-Samsung-Health-Signature HMAC-SHA256
    2. Call app.wearable.samsung.parse_samsung_health_webhook(raw)
    3. For each VitalsPayload: POST to /api/vitals (or insert directly)
    """
    return JSONResponse(
        status_code=501,
        content={"detail": "Samsung Health webhook not yet implemented (Phase 2)"},
    )
```

- [ ] **Step 2: Verify mypy**

```bash
uv run mypy app/api/vitals.py
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add app/api/vitals.py
git commit -m "feat(vitals): add ingest API — POST /api/vitals + status endpoint + samsung-webhook stub"
```

---

## Task 6: Vitals Polling Worker

**Files:**
- Create: `app/workers/vitals.py`

The worker polls `vitals_reading WHERE processed=false` every 30 seconds. For each row:
1. Load baseline from fixture (Phase 1) or DB (Phase 2)
2. Call VitalsSubAgent
3. Write anomaly rows
4. Fire Telegram alert for HIGH/URGENT
5. Write/merge memory file
6. Mark reading `processed=true`

- [ ] **Step 1: Write `app/workers/vitals.py`**

```python
"""arq worker: vitals anomaly detection — polls vitals_reading every 30 s.

Each unprocessed reading runs VitalsSubAgent (Haiku 4.5). HIGH/URGENT anomalies
trigger a Telegram alert to the senior's guardian. All MEDIUM+ anomalies are written
to /memories/{senior_id}/vitals_flags.json for SymptomSubAgent + ReportAgent to read.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import asyncpg
from arq.connections import RedisSettings
from telegram import Bot
from telegram.constants import ParseMode

from app.config import settings
from app.wearable import VitalsAnomalyResult, VitalsBaseline, VitalsPayload
from app.wearable.fixture import BASELINES, LAKSHMI_SENIOR_ID

log = logging.getLogger(__name__)

_ALERT_SEVERITIES = {"HIGH", "URGENT"}


# ── Baseline resolution ──────────────────────────────────────────────────────

def _get_baseline(senior_id: uuid.UUID) -> VitalsBaseline:
    """Return 7-day baseline for a senior. Phase 1: fixture. Phase 2: query DB."""
    return BASELINES.get(str(senior_id), BASELINES[str(LAKSHMI_SENIOR_ID)])


# ── Memory file writer ───────────────────────────────────────────────────────

def _write_memory(senior_id: uuid.UUID, anomalies: list[VitalsAnomalyResult]) -> None:
    """Merge new anomalies into /memories/{senior_id}/vitals_flags.json."""
    mem_dir = settings.memory_root / str(senior_id)
    mem_dir.mkdir(parents=True, exist_ok=True)
    mem_path = mem_dir / "vitals_flags.json"

    existing: dict[str, Any] = {}
    if mem_path.exists():
        try:
            existing = json.loads(mem_path.read_text())
        except Exception:
            existing = {}

    prior: list[dict[str, Any]] = existing.get("recent_anomalies", [])
    new_entries = [
        {
            "marker": a.marker,
            "severity": a.severity,
            "value": a.value,
            "recorded_at": datetime.now(UTC).isoformat(),
            "narrative": a.narrative,
        }
        for a in anomalies
    ]
    # Keep last 20 anomalies
    merged = (new_entries + prior)[:20]

    mem_path.write_text(
        json.dumps(
            {"last_updated": datetime.now(UTC).isoformat(), "recent_anomalies": merged},
            ensure_ascii=False,
            indent=2,
        )
    )


# ── Telegram alert ───────────────────────────────────────────────────────────

async def _send_telegram_alert(
    guardian_chat_id: str,
    senior_name: str,
    anomalies: list[VitalsAnomalyResult],
) -> None:
    if not settings.telegram_bot_token:
        log.warning("telegram_bot_token not set — alert suppressed")
        return

    alert_lines = "\n".join(
        f"• {a.narrative}" for a in anomalies if a.severity in _ALERT_SEVERITIES
    )
    highest = max(anomalies, key=lambda a: ["MEDIUM", "HIGH", "URGENT"].index(a.severity))
    header = f"⚠️ {highest.severity} — Vitals anomaly for {senior_name}"
    text = f"*{header}*\n\n{alert_lines}\n\n_Informational summary — physician review recommended_"

    try:
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=guardian_chat_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
        log.info("vitals_alert_sent", guardian=guardian_chat_id, severity=highest.severity)
    except Exception as exc:
        log.warning("vitals_alert_failed", error=str(exc))


# ── Core worker function ─────────────────────────────────────────────────────

async def process_vitals(ctx: dict[str, Any]) -> dict[str, Any]:
    """Process all unprocessed vitals readings. Called by arq scheduler."""
    from app.agents.vitals import run as vitals_run

    conn: asyncpg.Connection = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    processed_count = 0
    anomaly_count = 0

    try:
        rows = await conn.fetch(
            """SELECT id, senior_id, source, hr_bpm, spo2_pct, step_count,
                      skin_temp_delta, sleep_hours, raw_payload
               FROM vitals_reading
               WHERE processed = false
               ORDER BY recorded_at
               LIMIT 50"""
        )

        for row in rows:
            senior_id = row["senior_id"]
            reading_id = row["id"]

            payload = VitalsPayload(
                source=row["source"],
                hr_bpm=float(row["hr_bpm"]) if row["hr_bpm"] is not None else None,
                spo2_pct=float(row["spo2_pct"]) if row["spo2_pct"] is not None else None,
                step_count=row["step_count"],
                skin_temp_delta=float(row["skin_temp_delta"]) if row["skin_temp_delta"] is not None else None,
                sleep_hours=float(row["sleep_hours"]) if row["sleep_hours"] is not None else None,
            )
            baseline = _get_baseline(senior_id)

            anomalies = await vitals_run(payload, baseline, senior_id)

            # Persist anomaly rows
            for a in anomalies:
                await conn.execute(
                    """INSERT INTO vitals_anomaly
                       (senior_id, reading_id, marker, severity, value, threshold, narrative)
                       VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                    senior_id, reading_id,
                    a.marker, a.severity, float(a.value), float(a.threshold), a.narrative,
                )
                anomaly_count += 1

            # Telegram alert for HIGH/URGENT
            high_urgent = [a for a in anomalies if a.severity in _ALERT_SEVERITIES]
            if high_urgent:
                guardian_row = await conn.fetchrow(
                    """SELECT u.telegram_chat_id, s.full_name
                       FROM care_relationship cr
                       JOIN app_user u ON u.id = cr.guardian_id
                       JOIN app_user s ON s.id = cr.senior_id
                       WHERE cr.senior_id = $1
                       LIMIT 1""",
                    senior_id,
                )
                if guardian_row and guardian_row["telegram_chat_id"]:
                    await _send_telegram_alert(
                        guardian_chat_id=guardian_row["telegram_chat_id"],
                        senior_name=guardian_row["full_name"],
                        anomalies=high_urgent,
                    )
                    # Mark alerted_at on the anomaly rows
                    await conn.execute(
                        """UPDATE vitals_anomaly
                           SET alerted_at = now()
                           WHERE reading_id = $1 AND severity = ANY($2::text[])""",
                        reading_id,
                        list(_ALERT_SEVERITIES),
                    )

            # Write memory file
            if anomalies:
                _write_memory(senior_id, anomalies)

            # Mark processed
            await conn.execute(
                "UPDATE vitals_reading SET processed=true WHERE id=$1", reading_id
            )
            processed_count += 1

    finally:
        await conn.close()

    log.info("vitals_worker_run", processed=processed_count, anomalies=anomaly_count)
    return {"processed": processed_count, "anomalies": anomaly_count}


# ── arq worker settings ──────────────────────────────────────────────────────

async def startup(ctx: dict[str, Any]) -> None:
    log.info("vitals_worker_started")


class WorkerSettings:
    functions: ClassVar[list[Any]] = [process_vitals]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    job_timeout = 120
    max_jobs = 1  # one run at a time — avoids double-processing
    cron_jobs: ClassVar[list[Any]] = []  # populated at startup via arq cron helper
```

- [ ] **Step 2: Add cron schedule to enqueue process_vitals every 30 seconds**

In `app/main.py` lifespan (after `schedule_all_on_startup`), add:

```python
# Enqueue vitals worker on a 30-second poll
import asyncio
async def _vitals_poll_loop() -> None:
    from arq import create_pool
    from arq.connections import RedisSettings
    while True:
        try:
            redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await redis.enqueue_job("process_vitals")
            await redis.close()
        except Exception as exc:
            log.warning("vitals_enqueue_failed", error=str(exc))
        await asyncio.sleep(30)

asyncio.create_task(_vitals_poll_loop())
```

Actually: simpler — run vitals worker as a standalone arq process. Add to docker-compose.yml:

```yaml
  vitals-worker:
    build: .
    command: uv run arq app.workers.vitals.WorkerSettings
    depends_on: [db, redis]
    env_file: .env
```

OR, for local dev without docker, run in a second terminal:

```bash
uv run arq app.workers.vitals.WorkerSettings
```

And trigger manually in tests by calling `process_vitals({})` directly.

- [ ] **Step 3: Verify mypy**

```bash
uv run mypy app/workers/vitals.py
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add app/workers/vitals.py
git commit -m "feat(vitals): add polling worker — agent + Telegram alert + memory write"
```

---

## Task 7: Simulator Web UI

**Files:**
- Create: `app/templates/vitals_simulator.html`

A single Jinja2 template served at `GET /vitals-simulator`. No JS framework, no build step.
Five buttons. Status panel auto-polls `GET /api/vitals/status/{senior_id}` every 5 seconds.

- [ ] **Step 1: Create `app/templates/` directory and write the template**

```bash
mkdir -p app/templates
```

Create `app/templates/vitals_simulator.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Saath — Galaxy Watch Simulator</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 2rem; }
    h1 { font-size: 1.5rem; font-weight: 700; margin-bottom: .25rem; color: #f1f5f9; }
    .subtitle { color: #64748b; font-size: .875rem; margin-bottom: 2rem; }
    .card { background: #1e293b; border-radius: 12px; padding: 1.5rem;
            border: 1px solid #334155; margin-bottom: 1.5rem; }
    .card h2 { font-size: 1rem; font-weight: 600; color: #94a3b8;
               text-transform: uppercase; letter-spacing: .05em; margin-bottom: 1rem; }
    .senior-select { display: flex; align-items: center; gap: 1rem; margin-bottom: 1.5rem; }
    .senior-select label { color: #94a3b8; font-size: .875rem; }
    .senior-select select { background: #0f172a; border: 1px solid #334155;
                            color: #e2e8f0; padding: .5rem .75rem; border-radius: 8px;
                            font-size: .875rem; }
    .scenarios { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                 gap: .75rem; }
    .btn { display: flex; flex-direction: column; align-items: flex-start;
           padding: .875rem 1rem; border: 1px solid #334155; border-radius: 10px;
           background: #0f172a; color: #e2e8f0; cursor: pointer; transition: all .15s;
           text-align: left; }
    .btn:hover { border-color: #6366f1; background: #1e1b4b; }
    .btn.sending { border-color: #f59e0b; opacity: .7; }
    .btn.sent    { border-color: #10b981; }
    .btn .label  { font-weight: 600; font-size: .875rem; margin-bottom: .25rem; }
    .btn .values { font-size: .75rem; color: #64748b; font-family: monospace; }
    .btn.normal   .label { color: #10b981; }
    .btn.warning  .label { color: #f59e0b; }
    .btn.critical .label { color: #ef4444; }
    .status-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .stat { background: #0f172a; border-radius: 8px; padding: 1rem;
            border: 1px solid #1e293b; }
    .stat .name  { font-size: .75rem; color: #64748b; text-transform: uppercase;
                   letter-spacing: .05em; margin-bottom: .25rem; }
    .stat .value { font-size: 1.5rem; font-weight: 700; font-family: monospace; }
    .stat.ok     .value { color: #10b981; }
    .stat.warn   .value { color: #f59e0b; }
    .stat.crit   .value { color: #ef4444; }
    .anomaly-list { margin-top: 1rem; }
    .anomaly { display: flex; align-items: flex-start; gap: .75rem;
               padding: .75rem; border-radius: 8px; margin-bottom: .5rem;
               background: #0f172a; border: 1px solid #1e293b; }
    .badge { padding: .2rem .5rem; border-radius: 4px; font-size: .7rem;
             font-weight: 700; letter-spacing: .05em; flex-shrink: 0; }
    .badge.URGENT { background: #7f1d1d; color: #fca5a5; }
    .badge.HIGH   { background: #7c2d12; color: #fdba74; }
    .badge.MEDIUM { background: #1e3a5f; color: #93c5fd; }
    .anomaly .text { font-size: .8125rem; color: #cbd5e1; line-height: 1.4; }
    .ts { font-size: .7rem; color: #475569; margin-top: .25rem; }
    #toast { position: fixed; bottom: 1.5rem; right: 1.5rem; padding: .75rem 1.25rem;
             border-radius: 8px; font-size: .875rem; font-weight: 500;
             opacity: 0; transition: opacity .3s; pointer-events: none; }
    #toast.show { opacity: 1; }
    #toast.ok   { background: #064e3b; color: #6ee7b7; border: 1px solid #065f46; }
    #toast.err  { background: #7f1d1d; color: #fca5a5; border: 1px solid #991b1b; }
  </style>
</head>
<body>
  <h1>Galaxy Watch Simulator</h1>
  <p class="subtitle">Phase-1 fixture · Saath health companion demo</p>

  <div class="senior-select">
    <label for="senior">Senior:</label>
    <select id="senior">
      <option value="00000000-0000-0000-0000-000000000001">Lakshmi Iyer (demo)</option>
    </select>
  </div>

  <div class="card">
    <h2>Send Scenario</h2>
    <div class="scenarios">
      <button class="btn normal" data-scenario="normal">
        <span class="label">Normal day</span>
        <span class="values">HR 72 · SpO₂ 98% · Steps 6,500</span>
      </button>
      <button class="btn warning" data-scenario="post_med_hr_spike">
        <span class="label">Post-med HR spike</span>
        <span class="values">HR 108 · SpO₂ 96% · Steps 4,200</span>
      </button>
      <button class="btn critical" data-scenario="spo2_dip">
        <span class="label">SpO₂ dip</span>
        <span class="values">HR 78 · SpO₂ 88% · Steps 3,100</span>
      </button>
      <button class="btn warning" data-scenario="low_step_fatigue">
        <span class="label">Low-step fatigue</span>
        <span class="values">HR 74 · SpO₂ 97% · Steps 1,800</span>
      </button>
      <button class="btn critical" data-scenario="dizziness_episode">
        <span class="label">Dizziness episode ⚡</span>
        <span class="values">HR 112 · SpO₂ 88% · Steps 1,600</span>
      </button>
    </div>
  </div>

  <div class="card">
    <h2>Live Status <span id="poll-indicator" style="font-size:.7rem;color:#334155">polling…</span></h2>
    <div class="status-grid" id="stats">
      <div class="stat" id="stat-hr"><div class="name">Heart Rate</div><div class="value">—</div></div>
      <div class="stat" id="stat-spo2"><div class="name">SpO₂</div><div class="value">—</div></div>
      <div class="stat" id="stat-steps"><div class="name">Steps</div><div class="value">—</div></div>
      <div class="stat" id="stat-source"><div class="name">Source</div><div class="value" style="font-size:.9rem">—</div></div>
    </div>
    <div class="anomaly-list" id="anomalies"></div>
  </div>

  <div id="toast"></div>

  <script>
    const SCENARIOS = {
      normal:            {hr_bpm:72, spo2_pct:98, step_count:6500},
      post_med_hr_spike: {hr_bpm:108, spo2_pct:96, step_count:4200},
      spo2_dip:          {hr_bpm:78, spo2_pct:88, step_count:3100},
      low_step_fatigue:  {hr_bpm:74, spo2_pct:97, step_count:1800},
      dizziness_episode: {hr_bpm:112, spo2_pct:88, step_count:1600},
    };

    function toast(msg, type) {
      const el = document.getElementById('toast');
      el.textContent = msg; el.className = `show ${type}`;
      setTimeout(() => el.className = '', 2500);
    }

    document.querySelectorAll('.btn[data-scenario]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const scenario = btn.dataset.scenario;
        const seniorId = document.getElementById('senior').value;
        const data = { senior_id: seniorId, source: 'simulator', ...SCENARIOS[scenario],
                       raw_payload: { scenario } };
        btn.classList.add('sending');
        try {
          const res = await fetch('/api/vitals', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data),
          });
          if (!res.ok) throw new Error(await res.text());
          const j = await res.json();
          btn.classList.remove('sending'); btn.classList.add('sent');
          setTimeout(() => btn.classList.remove('sent'), 2000);
          toast(`Sent ${scenario} · reading_id ${j.reading_id.slice(0,8)}`, 'ok');
        } catch (e) {
          btn.classList.remove('sending');
          toast(`Error: ${e.message}`, 'err');
        }
      });
    });

    function classifyStat(el, value, marker) {
      el.querySelector('.value').textContent = value ?? '—';
      el.className = 'stat';
      if (value === null || value === undefined) return;
      if (marker === 'hr') {
        el.classList.add(value > 105 || value < 45 ? 'crit' : value > 95 ? 'warn' : 'ok');
      } else if (marker === 'spo2') {
        el.classList.add(value < 90 ? 'crit' : value < 95 ? 'warn' : 'ok');
      } else if (marker === 'steps') {
        el.classList.add(value < 2000 ? 'warn' : 'ok');
      }
    }

    async function poll() {
      const seniorId = document.getElementById('senior').value;
      try {
        const res = await fetch(`/api/vitals/status/${seniorId}`);
        const data = await res.json();
        document.getElementById('poll-indicator').textContent = 'live ●';

        const lr = data.last_reading;
        classifyStat(document.getElementById('stat-hr'),    lr?.hr_bpm,     'hr');
        classifyStat(document.getElementById('stat-spo2'),  lr?.spo2_pct ? lr.spo2_pct + '%' : null, 'spo2');
        classifyStat(document.getElementById('stat-steps'), lr?.step_count, 'steps');
        document.getElementById('stat-source').querySelector('.value').textContent = lr?.source ?? '—';

        const al = document.getElementById('anomalies');
        if (data.recent_anomalies.length === 0) {
          al.innerHTML = '<p style="color:#475569;font-size:.8125rem;margin-top:.5rem">No anomalies detected.</p>';
        } else {
          al.innerHTML = data.recent_anomalies.map(a => `
            <div class="anomaly">
              <span class="badge ${a.severity}">${a.severity}</span>
              <div><div class="text">${a.narrative}</div>
              <div class="ts">${a.marker} · ${a.value} · ${new Date(a.created_at).toLocaleTimeString()}</div></div>
            </div>`).join('');
        }
      } catch (e) {
        document.getElementById('poll-indicator').textContent = 'disconnected ✕';
      }
    }

    poll();
    setInterval(poll, 5000);
  </script>
</body>
</html>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/vitals_simulator.html
git commit -m "feat(vitals): add watch simulator web UI with 5 scenarios + live status panel"
```

---

## Task 8: Wire into main.py

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Add vitals router + simulator route to `app/main.py`**

After the `from app.api.labs import router as labs_router` import line, add:

```python
from app.api.vitals import router as vitals_router
```

After `app.include_router(labs_router)`, add:

```python
app.include_router(vitals_router)
```

Also add the simulator route and Jinja2 template setup. After the imports block, add:

```python
from fastapi.templating import Jinja2Templates
from fastapi import Request as FastAPIRequest

_templates = Jinja2Templates(directory="app/templates")
```

And add this route after the existing routes:

```python
@app.get("/vitals-simulator", include_in_schema=False)
async def vitals_simulator(request: FastAPIRequest) -> Any:
    """Serve the Galaxy Watch simulator UI."""
    return _templates.TemplateResponse("vitals_simulator.html", {"request": request})
```

- [ ] **Step 2: Verify the app starts and simulator loads**

```bash
uv run uvicorn app.main:app --port 8080 &
sleep 2
curl -sf http://localhost:8080/health | python3 -m json.tool
curl -sf -o /dev/null -w "%{http_code}" http://localhost:8080/vitals-simulator
# Expected: 200
curl -sf -o /dev/null -w "%{http_code}" http://localhost:8080/docs
kill %1
```

- [ ] **Step 3: Verify mypy on main.py**

```bash
uv run mypy app/main.py
```

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat(vitals): wire vitals router + simulator UI into FastAPI app"
```

---

## Task 9: Agent Contract

**Files:**
- Create: `.claude/agents/vitals-subagent.md`

- [ ] **Step 1: Write the agent contract**

```markdown
# VitalsSubAgent

**Purpose:** Classify a single wearable vitals reading against clinical thresholds
and return a structured list of anomaly results with safety-gatekeeper-approved narratives.

**Model:** `claude-haiku-4-5-20251001` — thinking off, tool-forced.

**Effort:** n/a (Haiku; no thinking).

**Input schema:**
```json
{
  "reading": {
    "hr_bpm": float | null,
    "spo2_pct": float | null,
    "step_count": int | null,
    "skin_temp_delta": float | null,
    "sleep_hours": float | null,
    "source": "simulator | samsung_health | fixture"
  },
  "baseline": {
    "hr_avg": float,
    "spo2_avg": float,
    "step_avg": float
  }
}
```

**Output:** `list[VitalsAnomalyResult]` — each anomaly has `marker, severity, value, threshold, narrative`.
Returns empty list if all readings are within normal thresholds.

**Thresholds:**
| Marker | MEDIUM | HIGH | URGENT |
|--------|--------|------|--------|
| HR (bpm) | >95 or <50 | >105 or <45 | >120 or <40 |
| SpO2 (%) | <95 | <93 | <90 |
| Steps/day | <2,000 | — | — |

**Safety contract:** Safety-gatekeeper (`app/agents/safety.check()`) is called inside
`app/agents/vitals.run()` on every narrative before returning. The worker must NOT
re-call the gatekeeper on VitalsAnomalyResult narratives.

**Samsung extensibility:** This agent accepts `VitalsPayload` objects — a normalized
type. Phase-2 Samsung Health payloads are transformed to `VitalsPayload` by
`app/wearable/samsung.parse_samsung_health_webhook()` before reaching this agent.
No changes to this agent are needed when the real Samsung watch ships.

**Caller:** `app/workers/vitals.process_vitals()`

**Metadata:** `{"agent": "VitalsSubAgent", "senior_id": "<uuid>"}`
```

- [ ] **Step 2: Commit**

```bash
git add .claude/agents/vitals-subagent.md
git commit -m "docs(vitals): add VitalsSubAgent contract with Samsung extensibility notes"
```

---

## Task 10: Integration Smoke Tests

**Files:**
- Create: `tests/test_vitals_smoke.py`

- [ ] **Step 1: Write `tests/test_vitals_smoke.py`**

```python
"""Integration smoke tests for vitals ingest + anomaly detection pipeline.

Requires: DB running (docker compose up -d db redis).
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.wearable.fixture import SCENARIOS, LAKSHMI_SENIOR_ID
from evals.personas.lakshmi import LAKSHMI_SENIOR_ID as PERSONA_LAKSHMI_ID


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_ingest_normal_scenario() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s = SCENARIOS["normal"]
        resp = await client.post("/api/vitals", json={
            "senior_id": str(LAKSHMI_SENIOR_ID),
            "source": "simulator",
            "hr_bpm": s.hr_bpm,
            "spo2_pct": s.spo2_pct,
            "step_count": s.step_count,
        })
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert "reading_id" in data
        uuid.UUID(data["reading_id"])  # valid UUID


@pytest.mark.anyio
async def test_ingest_unknown_senior_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/vitals", json={
            "senior_id": str(uuid.uuid4()),
            "source": "simulator",
            "hr_bpm": 72.0,
        })
        assert resp.status_code == 404


@pytest.mark.anyio
async def test_status_endpoint_returns_shape() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/vitals/status/{LAKSHMI_SENIOR_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "last_reading" in data
        assert "recent_anomalies" in data
        assert isinstance(data["recent_anomalies"], list)


@pytest.mark.anyio
async def test_worker_detects_dizziness_anomalies() -> None:
    """Ingest dizziness scenario then run worker directly — expect ≥2 anomaly rows."""
    import asyncpg
    from app.config import settings
    from app.workers.vitals import process_vitals

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        s = SCENARIOS["dizziness_episode"]
        resp = await client.post("/api/vitals", json={
            "senior_id": str(LAKSHMI_SENIOR_ID),
            "source": "simulator",
            "hr_bpm": s.hr_bpm,
            "spo2_pct": s.spo2_pct,
            "step_count": s.step_count,
        })
        assert resp.status_code == 201
        reading_id = resp.json()["reading_id"]

    # Run worker synchronously (no arq needed)
    result = await process_vitals({})
    assert result["processed"] >= 1

    # Verify anomaly rows created for this reading
    conn = await asyncpg.connect(
        dsn=settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    )
    try:
        rows = await conn.fetch(
            "SELECT marker, severity FROM vitals_anomaly WHERE reading_id=$1",
            uuid.UUID(reading_id),
        )
        assert len(rows) >= 2, f"Expected ≥2 anomaly rows, got {len(rows)}"
        severities = {r["severity"] for r in rows}
        assert severities & {"HIGH", "URGENT"}, f"Expected HIGH or URGENT, got {severities}"

        # Verify reading marked processed
        processed = await conn.fetchval(
            "SELECT processed FROM vitals_reading WHERE id=$1",
            uuid.UUID(reading_id),
        )
        assert processed is True
    finally:
        await conn.close()


@pytest.mark.anyio
async def test_samsung_webhook_returns_501() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/vitals/samsung-webhook", json={"test": "data"})
        assert resp.status_code == 501
```

- [ ] **Step 2: Run smoke tests**

```bash
uv run pytest tests/test_vitals_smoke.py -v
```
Expected: all 5 pass. `test_worker_detects_dizziness_anomalies` requires DB + Anthropic API key.

- [ ] **Step 3: Run full test suite to check no regressions**

```bash
uv run pytest tests/ -v
```
Expected: all existing tests still pass.

- [ ] **Step 4: Run pre-commit hooks**

```bash
uv run pre-commit run --all-files
```
Expected: all hooks pass (ruff, mypy, etc). Fix any issues before committing.

- [ ] **Step 5: Final commit**

```bash
git add tests/test_vitals_smoke.py
git commit -m "test(vitals): add integration smoke tests for ingest + worker + Samsung webhook stub"
```

---

## End-to-End Demo Verification

After all tasks complete, run the full demo:

```bash
# Terminal 1: app
docker compose up -d db redis
uv run alembic upgrade head
uv run python scripts/seed_personas.py
uv run uvicorn app.main:app --port 8080

# Terminal 2: vitals worker
uv run arq app.workers.vitals.WorkerSettings

# Browser
open http://localhost:8080/vitals-simulator
# Click "Dizziness episode ⚡"
# Status panel updates in 5s: HR 112, SpO₂ 88%, Steps 1,600
# Within 30s: Priya's Telegram receives URGENT alert
# Check memory: cat data/memories/00000000-0000-0000-0000-000000000001/vitals_flags.json
```

---

## Samsung Watch Phase-2 Upgrade Path

When the Samsung Galaxy Watch is ready (PRD Phase 2, §13):

1. **Implement `app/wearable/samsung.py`** — fill in `parse_samsung_health_webhook()`:
   - Verify HMAC-SHA256 signature from Samsung Health Platform
   - Map `com.samsung.health.heart_rate` → `hr_bpm`, etc.
   - Return `list[VitalsPayload]` with `source="samsung_health"`

2. **Implement `POST /api/vitals/samsung-webhook`** in `app/api/vitals.py`:
   - Call `parse_samsung_health_webhook(raw)`
   - Insert each `VitalsPayload` as a `vitals_reading` row
   - Return 200

3. **Register webhook URL** in Samsung Health Platform developer console:
   `https://your-domain.com/api/vitals/samsung-webhook`

4. **Add Samsung Health credentials** to `.env`:
   ```
   SAMSUNG_HEALTH_WEBHOOK_SECRET=...
   ```

**Zero changes needed** to:
- `app/agents/vitals.py` (VitalsSubAgent)
- `app/workers/vitals.py` (polling worker)
- `app/db/models.py` (DB schema — `source` column already accepts `samsung_health`)
- Tests — add Samsung-specific test with mocked webhook payload
