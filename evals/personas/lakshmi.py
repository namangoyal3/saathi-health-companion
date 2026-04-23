"""Canonical demo persona: Lakshmi Iyer, 71F, Bengaluru.

Stable UUIDs — every test, seed, and demo references these exact rows.
Do NOT change the UUIDs.

Conditions: T2DM + HTN + Hypothyroidism + CKD-3a
Medications: 7 active
Lab timeline: 4 quarterly panels, eGFR 78→71→65→58
Symptoms: 3 post-AM-dose dizziness + 2 breathlessness events
"""

import uuid
from datetime import date
from decimal import Decimal

from evals.personas.base import (
    BiomarkerFixture,
    LabPanelFixture,
    MedFixture,
    PersonaFixture,
    SymptomFixture,
)

LAKSHMI_SENIOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
PRIYA_GUARDIAN_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")

LAKSHMI = PersonaFixture(
    senior_id=LAKSHMI_SENIOR_ID,
    full_name="Lakshmi Iyer",
    role="senior",
    language="ta",
    timezone="Asia/Kolkata",
    phone="+919876543210",
    email=None,
    conditions=["T2DM", "HTN", "Hypothyroidism", "CKD_3a"],
    medications=[
        MedFixture(
            name="Metformin",
            dose_mg=Decimal("500"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8,20",
            start_date=date(2022, 3, 1),
            prescriber="Dr. Ramesh Iyer, Endocrinologist",
        ),
        MedFixture(
            name="Amlodipine",
            dose_mg=Decimal("5"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8",
            start_date=date(2021, 6, 15),
            prescriber="Dr. Sunita Rao, Cardiologist",
        ),
        MedFixture(
            name="Telmisartan",
            dose_mg=Decimal("40"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8",
            start_date=date(2021, 6, 15),
            prescriber="Dr. Sunita Rao, Cardiologist",
        ),
        MedFixture(
            name="Levothyroxine",
            dose_mg=Decimal("50"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=7",  # 30 min before breakfast
            start_date=date(2020, 11, 1),
            prescriber="Dr. Ramesh Iyer, Endocrinologist",
        ),
        MedFixture(
            name="Rosuvastatin",
            dose_mg=Decimal("10"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=21",
            start_date=date(2022, 1, 10),
            prescriber="Dr. Sunita Rao, Cardiologist",
        ),
        MedFixture(
            name="Aspirin",
            dose_mg=Decimal("75"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8",
            start_date=date(2021, 6, 15),
            prescriber="Dr. Sunita Rao, Cardiologist",
        ),
        MedFixture(
            name="Calcium + Vitamin D3",
            dose_mg=Decimal("500"),  # Ca element
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=13",
            start_date=date(2023, 2, 20),
            prescriber="Dr. Ramesh Iyer, Endocrinologist",
        ),
    ],
    lab_panels=[
        LabPanelFixture(
            panel_date=date(2024, 7, 10),
            lab_chain="thyrocare",
            biomarkers=[
                BiomarkerFixture("eGFR", Decimal("78"), "mL/min/1.73m²"),
                BiomarkerFixture("Creatinine", Decimal("0.9"), "mg/dL"),
                BiomarkerFixture("HbA1c", Decimal("7.4"), "%"),
                BiomarkerFixture("TSH", Decimal("2.8"), "mIU/L", "0.4-4.0"),
            ],
        ),
        LabPanelFixture(
            panel_date=date(2024, 10, 12),
            lab_chain="thyrocare",
            biomarkers=[
                BiomarkerFixture("eGFR", Decimal("71"), "mL/min/1.73m²"),
                BiomarkerFixture("Creatinine", Decimal("1.0"), "mg/dL"),
                BiomarkerFixture("HbA1c", Decimal("7.3"), "%"),
                BiomarkerFixture("TSH", Decimal("2.5"), "mIU/L", "0.4-4.0"),
            ],
        ),
        LabPanelFixture(
            panel_date=date(2025, 1, 12),
            lab_chain="drlal",
            biomarkers=[
                BiomarkerFixture("eGFR", Decimal("65"), "mL/min/1.73m²"),
                BiomarkerFixture("Creatinine", Decimal("1.1"), "mg/dL"),
                BiomarkerFixture("HbA1c", Decimal("7.2"), "%"),
                BiomarkerFixture("TSH", Decimal("2.1"), "mIU/L", "0.4-4.0"),
            ],
        ),
        LabPanelFixture(
            panel_date=date(2025, 4, 8),
            lab_chain="thyrocare",
            biomarkers=[
                BiomarkerFixture("eGFR", Decimal("58"), "mL/min/1.73m²"),
                BiomarkerFixture("Creatinine", Decimal("1.3"), "mg/dL"),
                BiomarkerFixture("HbA1c", Decimal("7.2"), "%"),
                BiomarkerFixture("TSH", Decimal("2.1"), "mIU/L", "0.4-4.0"),
            ],
        ),
    ],
    symptoms=[
        SymptomFixture(
            date=date(2025, 4, 4),
            symptom="dizziness",
            source="telegram",
            raw_text="dizzy after morning tablets",
        ),
        SymptomFixture(
            date=date(2025, 4, 11),
            symptom="dizziness",
            source="telegram",
            raw_text="dizzy again after tablets",
        ),
        SymptomFixture(
            date=date(2025, 4, 18),
            symptom="dizziness",
            source="ivr",
            raw_text="reported dizziness via IVR Flow C DTMF=1",
        ),
        SymptomFixture(
            date=date(2025, 3, 22),
            symptom="breathlessness",
            source="telegram",
            raw_text="feeling breathless climbing stairs",
        ),
        SymptomFixture(
            date=date(2025, 4, 1),
            symptom="breathlessness",
            source="telegram",
            raw_text="mild breathlessness, resting now",
        ),
    ],
)

PRIYA = PersonaFixture(
    senior_id=PRIYA_GUARDIAN_ID,
    full_name="Priya Iyer",
    role="guardian",
    language="en",
    timezone="America/Los_Angeles",
    phone="+14155550101",
    email="priya.iyer@example.com",
    conditions=[],
)
