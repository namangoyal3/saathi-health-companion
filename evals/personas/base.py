"""Shared types for synthetic persona fixtures."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class MedFixture:
    name: str
    dose_mg: Decimal
    frequency_rrule: str
    route: str = "oral"
    start_date: date | None = None
    prescriber: str | None = None


@dataclass
class BiomarkerFixture:
    name: str
    value: Decimal
    unit: str
    reference_range: str | None = None


@dataclass
class LabPanelFixture:
    panel_date: date
    lab_chain: str
    biomarkers: list[BiomarkerFixture] = field(default_factory=list)


@dataclass
class SymptomFixture:
    date: date
    symptom: str
    source: str  # telegram | ivr
    raw_text: str


@dataclass
class PersonaFixture:
    senior_id: uuid.UUID
    full_name: str
    role: str
    language: str
    timezone: str
    phone: str | None
    email: str | None
    conditions: list[str]
    medications: list[MedFixture] = field(default_factory=list)
    lab_panels: list[LabPanelFixture] = field(default_factory=list)
    symptoms: list[SymptomFixture] = field(default_factory=list)
