"""Test-only persona: Meera Sharma, 68F, Delhi.

Do NOT use Meera as a second canonical demo — PRD §3.2 says the demo stars Lakshmi.
Use Meera to validate that flows generalize beyond Lakshmi.

Conditions: T2DM + HTN only (no CKD, no thyroid)
Medications: 4 active
"""

import uuid
from datetime import date
from decimal import Decimal

from evals.personas.base import (
    MedFixture,
    PersonaFixture,
)

MEERA_SENIOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
MEERA_GUARDIAN_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")

MEERA = PersonaFixture(
    senior_id=MEERA_SENIOR_ID,
    full_name="Meera Sharma",
    role="senior",
    language="hi",
    timezone="Asia/Kolkata",
    phone="+911123456789",
    email=None,
    conditions=["T2DM", "HTN"],
    medications=[
        MedFixture(
            name="Metformin",
            dose_mg=Decimal("1000"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8,20",
            start_date=date(2021, 5, 10),
            prescriber="Dr. Anjali Gupta, General Physician",
        ),
        MedFixture(
            name="Glipizide",
            dose_mg=Decimal("5"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8",
            start_date=date(2022, 8, 1),
            prescriber="Dr. Anjali Gupta, General Physician",
        ),
        MedFixture(
            name="Amlodipine",
            dose_mg=Decimal("5"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8",
            start_date=date(2020, 3, 15),
            prescriber="Dr. Vikram Mehta, Cardiologist",
        ),
        MedFixture(
            name="Losartan",
            dose_mg=Decimal("50"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8",
            start_date=date(2020, 3, 15),
            prescriber="Dr. Vikram Mehta, Cardiologist",
        ),
    ],
)

MEERA_GUARDIAN = PersonaFixture(
    senior_id=MEERA_GUARDIAN_ID,
    full_name="Rahul Sharma",
    role="guardian",
    language="en",
    timezone="America/New_York",
    phone="+12125550202",
    email="rahul.sharma@example.com",
    conditions=[],
)
