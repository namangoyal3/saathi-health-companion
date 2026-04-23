"""Test persona: Rajesh, 55M, cardiovascular variant.

Exercises the Cardiology report variant (report_type="cardio").
Conditions: T2DM + HTN + CAD (Coronary Artery Disease)
Medications: 5 active (antiplatelet + statin + beta-blocker)
"""

import uuid
from datetime import date
from decimal import Decimal

from evals.personas.base import (
    BiomarkerFixture,
    LabPanelFixture,
    MedFixture,
    PersonaFixture,
)

RAJESH_SENIOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000005")

RAJESH = PersonaFixture(
    senior_id=RAJESH_SENIOR_ID,
    full_name="Rajesh Kumar",
    role="senior",
    language="en",
    timezone="Asia/Kolkata",
    phone="+919988776655",
    email="rajesh.kumar@example.com",
    conditions=["T2DM", "HTN", "CAD"],
    medications=[
        MedFixture(
            name="Metformin",
            dose_mg=Decimal("500"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8,20",
            start_date=date(2020, 1, 15),
            prescriber="Dr. Pradeep Singh, Cardiologist",
        ),
        MedFixture(
            name="Aspirin",
            dose_mg=Decimal("75"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8",
            start_date=date(2019, 6, 1),
            prescriber="Dr. Pradeep Singh, Cardiologist",
        ),
        MedFixture(
            name="Atorvastatin",
            dose_mg=Decimal("40"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=21",
            start_date=date(2019, 6, 1),
            prescriber="Dr. Pradeep Singh, Cardiologist",
        ),
        MedFixture(
            name="Metoprolol",
            dose_mg=Decimal("25"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8,20",
            start_date=date(2019, 6, 1),
            prescriber="Dr. Pradeep Singh, Cardiologist",
        ),
        MedFixture(
            name="Ramipril",
            dose_mg=Decimal("5"),
            frequency_rrule="RRULE:FREQ=DAILY;BYHOUR=8",
            start_date=date(2020, 3, 10),
            prescriber="Dr. Pradeep Singh, Cardiologist",
        ),
    ],
    lab_panels=[
        LabPanelFixture(
            panel_date=date(2025, 2, 14),
            lab_chain="metropolis",
            biomarkers=[
                BiomarkerFixture("HbA1c", Decimal("7.8"), "%"),
                BiomarkerFixture("LDL", Decimal("82"), "mg/dL"),
                BiomarkerFixture("HDL", Decimal("38"), "mg/dL"),
                BiomarkerFixture("Triglycerides", Decimal("195"), "mg/dL"),
                BiomarkerFixture("eGFR", Decimal("72"), "mL/min/1.73m²"),
                BiomarkerFixture("Creatinine", Decimal("1.0"), "mg/dL"),
            ],
        ),
    ],
)
