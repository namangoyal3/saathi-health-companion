"""Offline smoke tests for the vitals anomaly pipeline.

No live LLM — the agent's `run()` function is monkeypatched to return deterministic
anomalies so we can verify the persistence + Telegram + memory path end-to-end.

Live-LLM tests (where the actual Haiku classifier is invoked) live in a separate
file gated on ANTHROPIC_API_KEY being set.
"""

from __future__ import annotations

import datetime
import json
import uuid
from pathlib import Path
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from app.agents.vitals_anomaly import DailySummaryInput, VitalsAnomaly
from app.config import settings
from app.workers.vitals_anomaly import process_summary

# Stable senior UUID from evals/personas/base.py
LAKSHMI_SENIOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _pg_dsn() -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://")


@pytest_asyncio.fixture
async def seeded_lakshmi_summary() -> uuid.UUID:
    """Insert a dizziness-episode daily summary for Lakshmi on today's date."""
    conn = await asyncpg.connect(dsn=_pg_dsn())
    today = datetime.date.today()
    try:
        await conn.execute(
            """INSERT INTO wearable_daily_summary
               (senior_id, date, steps, avg_heart_rate, sleep_minutes,
                sleep_efficiency_pct, sleep_score, avg_spo2_pct,
                avg_skin_temp_c, hrv_rmssd, stress_score, exercise_minutes)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
               ON CONFLICT (senior_id, date) DO UPDATE SET
                 avg_heart_rate = EXCLUDED.avg_heart_rate,
                 avg_spo2_pct = EXCLUDED.avg_spo2_pct,
                 steps = EXCLUDED.steps,
                 sleep_minutes = EXCLUDED.sleep_minutes""",
            LAKSHMI_SENIOR_ID, today, 1600, 112, 270, 64, 48, 88, 37.1, 18, 78, 5,
        )
        # Clear any prior anomalies for today so the test is deterministic
        await conn.execute(
            "DELETE FROM vitals_anomaly WHERE senior_id=$1 AND summary_date=$2",
            LAKSHMI_SENIOR_ID, today,
        )
    finally:
        await conn.close()
    return LAKSHMI_SENIOR_ID


@pytest.mark.asyncio
async def test_process_summary_persists_anomalies_with_mocked_classifier(
    seeded_lakshmi_summary: uuid.UUID,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """With the classifier mocked, verify DB + memory + alerted_at get written correctly."""
    # Redirect memory root so we don't pollute dev data
    monkeypatch.setattr(settings, "memory_root", tmp_path)

    # Stub the Haiku classifier to return a deterministic set of anomalies
    async def fake_run(
        summary: DailySummaryInput, *, baseline_skin_temp_c: float | None = None
    ) -> list[VitalsAnomaly]:
        return [
            VitalsAnomaly(marker="avg_heart_rate", severity="HIGH", value=112.0,
                          threshold=105.0, narrative="Heart rate averaged 112 bpm, above the 105 bpm threshold."),
            VitalsAnomaly(marker="avg_spo2_pct", severity="URGENT", value=88.0,
                          threshold=90.0, narrative="SpO₂ averaged 88%, below the 90% threshold."),
            VitalsAnomaly(marker="steps", severity="MEDIUM", value=1600.0,
                          threshold=2000.0, narrative="Step count 1,600 is below the 2,000 daily threshold."),
        ]

    import app.workers.vitals_anomaly as worker_mod
    monkeypatch.setattr(worker_mod, "classify", fake_run)

    today = datetime.date.today()
    result = await process_summary(seeded_lakshmi_summary, today)

    assert result["anomaly_count"] == 3
    assert set(result["severities"]) == {"HIGH", "URGENT", "MEDIUM"}

    # Verify DB rows
    conn = await asyncpg.connect(dsn=_pg_dsn())
    try:
        rows = await conn.fetch(
            "SELECT marker, severity, alerted_at FROM vitals_anomaly "
            "WHERE senior_id=$1 AND summary_date=$2 ORDER BY marker",
            seeded_lakshmi_summary, today,
        )
        assert len(rows) == 3
        markers = {r["marker"] for r in rows}
        assert markers == {"avg_heart_rate", "avg_spo2_pct", "steps"}

        # URGENT + HIGH rows get alerted_at stamped (if Telegram is configured)
        # MEDIUM rows never do
        medium_row = next(r for r in rows if r["severity"] == "MEDIUM")
        assert medium_row["alerted_at"] is None
    finally:
        await conn.close()

    # Verify memory file was written
    mem_path = tmp_path / str(seeded_lakshmi_summary) / "vitals_flags.json"
    assert mem_path.exists()
    data = json.loads(mem_path.read_text())
    assert "recent_anomalies" in data
    assert len(data["recent_anomalies"]) == 3
    markers_in_mem = {a["marker"] for a in data["recent_anomalies"]}
    assert markers_in_mem == {"avg_heart_rate", "avg_spo2_pct", "steps"}


@pytest.mark.asyncio
async def test_process_summary_missing_summary_is_noop() -> None:
    """Running the detector on a date with no summary returns an empty result."""
    ghost_senior = uuid.UUID("deadbeef-0000-0000-0000-000000000000")
    # This senior isn't in app_user, but the detector handles missing summary gracefully
    result = await process_summary(ghost_senior, datetime.date(2020, 1, 1))
    assert result["anomaly_count"] == 0
    assert result["alerted"] is False


@pytest.mark.asyncio
async def test_normal_summary_produces_no_anomalies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify the empty-anomaly path: no DB rows, no memory write, no alert."""
    monkeypatch.setattr(settings, "memory_root", tmp_path)

    async def fake_run(
        summary: DailySummaryInput, *, baseline_skin_temp_c: float | None = None
    ) -> list[VitalsAnomaly]:
        return []

    import app.workers.vitals_anomaly as worker_mod
    monkeypatch.setattr(worker_mod, "classify", fake_run)

    # Seed a normal summary
    conn = await asyncpg.connect(dsn=_pg_dsn())
    today = datetime.date.today() - datetime.timedelta(days=1)
    try:
        await conn.execute(
            """INSERT INTO wearable_daily_summary
               (senior_id, date, steps, avg_heart_rate, avg_spo2_pct)
               VALUES ($1,$2,$3,$4,$5)
               ON CONFLICT (senior_id, date) DO UPDATE SET steps=EXCLUDED.steps""",
            LAKSHMI_SENIOR_ID, today, 6500, 72, 98,
        )
        await conn.execute(
            "DELETE FROM vitals_anomaly WHERE senior_id=$1 AND summary_date=$2",
            LAKSHMI_SENIOR_ID, today,
        )
    finally:
        await conn.close()

    result = await process_summary(LAKSHMI_SENIOR_ID, today)
    assert result["anomaly_count"] == 0

    # No memory file written when there are zero anomalies
    mem_path = tmp_path / str(LAKSHMI_SENIOR_ID) / "vitals_flags.json"
    assert not mem_path.exists()
