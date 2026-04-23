#!/usr/bin/env python3
"""Idempotent persona seed script.

Inserts Lakshmi (senior), Priya (guardian), Meera (senior + guardian),
and Rajesh (senior) with deterministic UUIDs. All inserts use
ON CONFLICT DO NOTHING — safe to run repeatedly.

Usage:
    uv run python scripts/seed_personas.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to sys.path so imports work without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncpg  # type: ignore[import]

import app.db.pg  # noqa: F401  — patches asyncpg.connect for Supabase pooler
from app.config import settings
from evals.personas.lakshmi import LAKSHMI, LAKSHMI_SENIOR_ID, PRIYA, PRIYA_GUARDIAN_ID
from evals.personas.meera import MEERA, MEERA_GUARDIAN, MEERA_GUARDIAN_ID, MEERA_SENIOR_ID
from evals.personas.rajesh import RAJESH, RAJESH_SENIOR_ID


async def seed(conn: asyncpg.Connection) -> None:  # type: ignore[type-arg]
    print("Seeding app_user rows...")
    await _upsert_user(conn, LAKSHMI)
    await _upsert_user(conn, PRIYA)
    await _upsert_user(conn, MEERA)
    await _upsert_user(conn, MEERA_GUARDIAN)
    await _upsert_user(conn, RAJESH)

    print("Seeding care_relationship rows...")
    await _upsert_relationship(
        conn,
        LAKSHMI_SENIOR_ID,
        PRIYA_GUARDIAN_ID,
        "daughter",
        {
            "health_summary": True,
            "medication_alerts": True,
            "lab_results": True,
            "ivr_transcripts": True,
            "doctor_reports": True,
        },
    )
    await _upsert_relationship(
        conn,
        MEERA_SENIOR_ID,
        MEERA_GUARDIAN_ID,
        "son",
        {
            "health_summary": True,
            "medication_alerts": True,
            "lab_results": False,
            "ivr_transcripts": False,
            "doctor_reports": True,
        },
    )

    print("Seeding Lakshmi medications...")
    for med in LAKSHMI.medications:
        await _upsert_medication(conn, LAKSHMI_SENIOR_ID, med)

    print("Seeding Meera medications...")
    for med in MEERA.medications:
        await _upsert_medication(conn, MEERA_SENIOR_ID, med)

    print("Seeding Rajesh medications...")
    for med in RAJESH.medications:
        await _upsert_medication(conn, RAJESH_SENIOR_ID, med)

    print("Seeding Lakshmi lab panels and biomarkers...")
    for panel in LAKSHMI.lab_panels:
        panel_id = await _upsert_lab_panel(conn, LAKSHMI_SENIOR_ID, panel)
        for bm in panel.biomarkers:
            await _upsert_biomarker(conn, panel_id, bm)

    print("Seeding Rajesh lab panels and biomarkers...")
    for panel in RAJESH.lab_panels:
        panel_id = await _upsert_lab_panel(conn, RAJESH_SENIOR_ID, panel)
        for bm in panel.biomarkers:
            await _upsert_biomarker(conn, panel_id, bm)

    print("Seeding Lakshmi symptom events...")
    for symptom in LAKSHMI.symptoms:
        await _upsert_symptom(conn, LAKSHMI_SENIOR_ID, symptom)

    print("Creating memory files...")
    _write_memory_profile(LAKSHMI)
    _write_memory_profile(MEERA)
    _write_memory_profile(RAJESH)

    print("Seed complete.")


async def _upsert_user(conn: asyncpg.Connection, persona: object) -> None:  # type: ignore[type-arg]
    from evals.personas.base import PersonaFixture

    assert isinstance(persona, PersonaFixture)
    await conn.execute(
        """
        INSERT INTO app_user (id, role, full_name, phone, email, language, timezone)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (id) DO NOTHING
        """,
        persona.senior_id,
        persona.role,
        persona.full_name,
        persona.phone,
        persona.email,
        persona.language,
        persona.timezone,
    )


async def _upsert_relationship(
    conn: asyncpg.Connection,  # type: ignore[type-arg]
    senior_id: object,
    guardian_id: object,
    label: str,
    consent: dict[str, bool],
) -> None:
    import json

    await conn.execute(
        """
        INSERT INTO care_relationship (senior_id, guardian_id, relationship_label, consent_matrix)
        VALUES ($1, $2, $3, $4::jsonb)
        ON CONFLICT ON CONSTRAINT uq_care_relationship_pair DO NOTHING
        """,
        senior_id,
        guardian_id,
        label,
        json.dumps(consent),
    )


async def _upsert_medication(
    conn: asyncpg.Connection,  # type: ignore[type-arg]
    senior_id: object,
    med: object,
) -> None:
    from evals.personas.base import MedFixture

    assert isinstance(med, MedFixture)
    await conn.execute(
        """
        INSERT INTO medication (senior_id, name, dose_mg, frequency_rrule, route, start_date, prescriber)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT ON CONSTRAINT uq_medication_senior_name DO NOTHING
        """,
        senior_id,
        med.name,
        med.dose_mg,
        med.frequency_rrule,
        med.route,
        med.start_date,
        med.prescriber,
    )


async def _upsert_lab_panel(
    conn: asyncpg.Connection,  # type: ignore[type-arg]
    senior_id: object,
    panel: object,
) -> object:
    from evals.personas.base import LabPanelFixture

    assert isinstance(panel, LabPanelFixture)
    row = await conn.fetchrow(
        """
        INSERT INTO lab_panel (senior_id, panel_date, lab_chain)
        VALUES ($1, $2, $3)
        ON CONFLICT ON CONSTRAINT uq_lab_panel_senior_date DO NOTHING
        RETURNING id
        """,
        senior_id,
        panel.panel_date,
        panel.lab_chain,
    )
    if row is None:
        # Already exists — fetch the id
        row = await conn.fetchrow(
            "SELECT id FROM lab_panel WHERE senior_id = $1 AND panel_date = $2",
            senior_id,
            panel.panel_date,
        )
    return row["id"]  # type: ignore[index]


async def _upsert_biomarker(
    conn: asyncpg.Connection,  # type: ignore[type-arg]
    panel_id: object,
    bm: object,
) -> None:
    from evals.personas.base import BiomarkerFixture

    assert isinstance(bm, BiomarkerFixture)
    await conn.execute(
        """
        INSERT INTO lab_biomarker (lab_panel_id, biomarker, value, unit, reference_range)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT ON CONSTRAINT uq_lab_biomarker_panel_name DO NOTHING
        """,
        panel_id,
        bm.name,
        bm.value,
        bm.unit,
        bm.reference_range,
    )


async def _upsert_symptom(
    conn: asyncpg.Connection,  # type: ignore[type-arg]
    senior_id: object,
    symptom: object,
) -> None:
    from evals.personas.base import SymptomFixture

    assert isinstance(symptom, SymptomFixture)
    from datetime import UTC, datetime

    received_at = datetime.combine(symptom.date, datetime.min.time()).replace(  # type: ignore[attr-defined]
        tzinfo=UTC
    )
    await conn.execute(
        """
        INSERT INTO telegram_inbound (senior_id, raw_text, message_type, source, intent, parsed_symptom, received_at)
        VALUES ($1, $2, 'text', $3, 'symptom_report', $4, $5)
        ON CONFLICT ON CONSTRAINT uq_telegram_inbound_symptom DO NOTHING
        """,
        senior_id,
        symptom.raw_text,
        symptom.source,
        symptom.symptom,
        received_at,
    )


def _write_memory_profile(persona: object) -> None:
    from evals.personas.base import PersonaFixture

    assert isinstance(persona, PersonaFixture)
    if persona.role != "senior":
        return
    root = settings.memory_root / str(persona.senior_id)
    root.mkdir(parents=True, exist_ok=True)

    conditions_str = ", ".join(persona.conditions)
    meds_str = "\n".join(
        f"- {m.name} {m.dose_mg}mg — {m.frequency_rrule}" for m in persona.medications
    )

    profile_text = f"""# {persona.full_name} — Profile

Role: {persona.role}
Language: {persona.language}
Timezone: {persona.timezone}
Conditions: {conditions_str}
Phone: {persona.phone or "—"}

## Active Medications

{meds_str}
"""
    (root / "profile.md").write_text(profile_text, encoding="utf-8")


async def main() -> None:
    # asyncpg uses raw postgres:// URL without SQLAlchemy driver prefix
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    try:
        await seed(conn)
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
