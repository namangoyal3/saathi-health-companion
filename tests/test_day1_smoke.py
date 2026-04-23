"""Day 1 acceptance smoke tests.

Assertions:
1. GET /health -> 200, version non-empty, models.opus == "claude-opus-4-7"
2. All 10 tables exist after alembic upgrade head
3. seed_personas.py run once -> correct row counts
4. seed_personas.py run again -> zero additional rows (idempotency)
5. Lakshmi's app_user row has correct language and timezone
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from evals.personas.lakshmi import LAKSHMI_SENIOR_ID

EXPECTED_TABLES = {
    "app_user",
    "care_relationship",
    "medication",
    "med_reminder_event",
    "lab_panel",
    "lab_biomarker",
    "ivr_call_log",
    "telegram_inbound",
    "agent_flag",
    "daily_summary",
    "doctor_report",
}


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] != ""
    assert data["models"]["opus"] == "claude-opus-4-7"
    assert data["models"]["haiku"] == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_all_tables_exist(db: AsyncSession) -> None:
    result = await db.execute(
        text(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            """
        )
    )
    tables = {row[0] for row in result.fetchall()}
    missing = EXPECTED_TABLES - tables
    assert not missing, f"Missing tables after migration: {missing}"


@pytest.mark.asyncio
async def test_seed_idempotency(db: AsyncSession) -> None:
    """Run seed script twice; counts must be identical after second run."""
    seed_path = Path(__file__).parent.parent / "scripts" / "seed_personas.py"

    def run_seed() -> int:
        result = subprocess.run(
            [sys.executable, str(seed_path)],
            capture_output=True,
            text=True,
        )
        return result.returncode

    assert run_seed() == 0, "First seed run failed"
    counts_after_first = await _get_counts(db)

    assert run_seed() == 0, "Second seed run failed"
    counts_after_second = await _get_counts(db)

    assert counts_after_first == counts_after_second, (
        f"Seed is not idempotent. Before: {counts_after_first}, After: {counts_after_second}"
    )


@pytest.mark.asyncio
async def test_lakshmi_row_correct(db: AsyncSession) -> None:
    result = await db.execute(
        text("SELECT language, timezone FROM app_user WHERE id = :id"),
        {"id": str(LAKSHMI_SENIOR_ID)},
    )
    row = result.fetchone()
    assert row is not None, "Lakshmi user row not found"
    assert row[0] == "ta", f"Expected language='ta', got {row[0]!r}"
    assert row[1] == "Asia/Kolkata", f"Expected timezone='Asia/Kolkata', got {row[1]!r}"


@pytest.mark.asyncio
async def test_lakshmi_medications_count(db: AsyncSession) -> None:
    result = await db.execute(
        text("SELECT COUNT(*) FROM medication WHERE senior_id = :id"),
        {"id": str(LAKSHMI_SENIOR_ID)},
    )
    count = result.scalar()
    assert count == 7, f"Expected 7 Lakshmi medications, got {count}"


@pytest.mark.asyncio
async def test_lakshmi_lab_panels_count(db: AsyncSession) -> None:
    result = await db.execute(
        text("SELECT COUNT(*) FROM lab_panel WHERE senior_id = :id"),
        {"id": str(LAKSHMI_SENIOR_ID)},
    )
    count = result.scalar()
    assert count == 4, f"Expected 4 Lakshmi lab panels, got {count}"


@pytest.mark.asyncio
async def test_lakshmi_biomarkers_count(db: AsyncSession) -> None:
    result = await db.execute(
        text(
            """
            SELECT COUNT(*) FROM lab_biomarker lb
            JOIN lab_panel lp ON lb.lab_panel_id = lp.id
            WHERE lp.senior_id = :id
            """
        ),
        {"id": str(LAKSHMI_SENIOR_ID)},
    )
    count = result.scalar()
    assert count == 16, f"Expected 16 Lakshmi biomarkers (4 panels x 4 each), got {count}"


async def _get_counts(db: AsyncSession) -> dict[str, int]:
    tables = [
        "app_user",
        "care_relationship",
        "medication",
        "lab_panel",
        "lab_biomarker",
        "telegram_inbound",
    ]
    counts: dict[str, int] = {}
    for table in tables:
        result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
        counts[table] = int(result.scalar() or 0)
    return counts
