"""SQLAlchemy 2.0 async ORM models — mirrors Tech Spec §2.1 DDL exactly."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    role: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # senior | guardian
    full_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(sa.String(20))
    email: Mapped[str | None] = mapped_column(sa.String(255))
    language: Mapped[str] = mapped_column(sa.String(10), nullable=False, server_default="en")
    timezone: Mapped[str] = mapped_column(sa.String(50), nullable=False, server_default="UTC")
    telegram_chat_id: Mapped[str | None] = mapped_column(sa.String(50))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    # relationships
    senior_relationships: Mapped[list[CareRelationship]] = relationship(
        "CareRelationship", foreign_keys="CareRelationship.senior_id", back_populates="senior"
    )
    guardian_relationships: Mapped[list[CareRelationship]] = relationship(
        "CareRelationship", foreign_keys="CareRelationship.guardian_id", back_populates="guardian"
    )
    medications: Mapped[list[Medication]] = relationship("Medication", back_populates="senior")
    lab_panels: Mapped[list[LabPanel]] = relationship("LabPanel", back_populates="senior")
    ivr_call_logs: Mapped[list[IVRCallLog]] = relationship("IVRCallLog", back_populates="senior")
    telegram_inbound: Mapped[list[TelegramInbound]] = relationship(
        "TelegramInbound", back_populates="senior"
    )
    agent_flags: Mapped[list[AgentFlag]] = relationship("AgentFlag", back_populates="senior")
    daily_summaries: Mapped[list[DailySummary]] = relationship(
        "DailySummary", back_populates="senior"
    )
    doctor_reports: Mapped[list[DoctorReport]] = relationship(
        "DoctorReport", back_populates="senior"
    )


class CareRelationship(Base):
    __tablename__ = "care_relationship"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    guardian_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    relationship_label: Mapped[str] = mapped_column(sa.String(50), nullable=False)  # daughter, son
    consent_matrix: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    senior: Mapped[AppUser] = relationship(
        "AppUser", foreign_keys=[senior_id], back_populates="senior_relationships"
    )
    guardian: Mapped[AppUser] = relationship(
        "AppUser", foreign_keys=[guardian_id], back_populates="guardian_relationships"
    )


class Medication(Base):
    __tablename__ = "medication"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    dose_mg: Mapped[float | None] = mapped_column(sa.Numeric(8, 2))
    frequency_rrule: Mapped[str | None] = mapped_column(sa.Text)  # RFC 5545 RRULE
    route: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="oral")
    start_date: Mapped[date | None] = mapped_column(sa.Date)
    end_date: Mapped[date | None] = mapped_column(sa.Date)
    prescriber: Mapped[str | None] = mapped_column(sa.Text)
    notes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    senior: Mapped[AppUser] = relationship("AppUser", back_populates="medications")
    reminder_events: Mapped[list[MedReminderEvent]] = relationship(
        "MedReminderEvent", back_populates="medication"
    )


class MedReminderEvent(Base):
    __tablename__ = "med_reminder_event"
    __table_args__ = (
        sa.Index("ix_med_reminder_event_senior_scheduled", "senior_id", "scheduled_for"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    medication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("medication.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_for: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    event: Mapped[str | None] = mapped_column(
        sa.String(30)
    )  # taken | missed | taken_via_ivr | snoozed
    event_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    ivr_call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    medication: Mapped[Medication] = relationship("Medication", back_populates="reminder_events")


class LabPanel(Base):
    __tablename__ = "lab_panel"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    panel_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    lab_chain: Mapped[str | None] = mapped_column(sa.String(50))
    pdf_path: Mapped[str | None] = mapped_column(sa.Text)
    parsed_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    mean_confidence: Mapped[float | None] = mapped_column(sa.Numeric(4, 3))
    extraction_method: Mapped[str | None] = mapped_column(sa.String(30))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    senior: Mapped[AppUser] = relationship("AppUser", back_populates="lab_panels")
    biomarkers: Mapped[list[LabBiomarker]] = relationship("LabBiomarker", back_populates="panel")


class LabBiomarker(Base):
    __tablename__ = "lab_biomarker"
    __table_args__ = (sa.Index("ix_lab_biomarker_panel_biomarker", "lab_panel_id", "biomarker"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    lab_panel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("lab_panel.id", ondelete="CASCADE"), nullable=False
    )
    biomarker: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    value: Mapped[float | None] = mapped_column(sa.Numeric(12, 4))
    value_text: Mapped[str | None] = mapped_column(sa.Text)  # for non-numeric values
    unit: Mapped[str | None] = mapped_column(sa.String(30))
    reference_range: Mapped[str | None] = mapped_column(sa.String(50))
    confidence: Mapped[float | None] = mapped_column(sa.Numeric(4, 3))

    panel: Mapped[LabPanel] = relationship("LabPanel", back_populates="biomarkers")


class IVRCallLog(Base):
    __tablename__ = "ivr_call_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # exotel | twilio | plivo
    call_sid: Mapped[str | None] = mapped_column(sa.String(100))
    flow: Mapped[str | None] = mapped_column(sa.String(5))  # A | B | C
    language: Mapped[str] = mapped_column(sa.String(10), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(30), nullable=False
    )  # queued|dialing|in_progress|resolved|partial|failed
    dtmf_responses: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    transcript: Mapped[str | None] = mapped_column(sa.Text)
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer)
    attempt_number: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")
    started_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    senior: Mapped[AppUser] = relationship("AppUser", back_populates="ivr_call_logs")


class TelegramInbound(Base):
    __tablename__ = "telegram_inbound"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    telegram_message_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    raw_text: Mapped[str | None] = mapped_column(sa.Text)
    message_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # text | voice | photo
    source: Mapped[str] = mapped_column(sa.String(20), nullable=False, server_default="telegram")
    intent: Mapped[str | None] = mapped_column(
        sa.String(50)
    )  # symptom_report | medication_query | general
    parsed_symptom: Mapped[str | None] = mapped_column(sa.Text)
    received_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    senior: Mapped[AppUser] = relationship("AppUser", back_populates="telegram_inbound")


class AgentFlag(Base):
    __tablename__ = "agent_flag"
    __table_args__ = (sa.Index("ix_agent_flag_senior_created", "senior_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    agent: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    severity: Mapped[str] = mapped_column(sa.String(10), nullable=False)  # HIGH | MEDIUM | LOW
    flag_type: Mapped[str] = mapped_column(
        sa.String(30), nullable=False
    )  # drug_drug | drug_lab | drug_symptom
    finding: Mapped[str] = mapped_column(sa.Text, nullable=False)
    drugs_involved: Mapped[list[str] | None] = mapped_column(JSONB)
    resolved: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default="false")
    resolved_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    senior: Mapped[AppUser] = relationship("AppUser", back_populates="agent_flags")


class DailySummary(Base):
    __tablename__ = "daily_summary"

    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("app_user.id", ondelete="CASCADE"),
        primary_key=True,
    )
    day: Mapped[date] = mapped_column(sa.Date, primary_key=True)
    brief_text: Mapped[str | None] = mapped_column(sa.Text)
    adherence_pct: Mapped[float | None] = mapped_column(sa.Numeric(5, 2))
    flags_count: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")
    data_sources: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    word_count: Mapped[int | None] = mapped_column(sa.Integer)
    generated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    senior: Mapped[AppUser] = relationship("AppUser", back_populates="daily_summaries")


class DoctorReport(Base):
    __tablename__ = "doctor_report"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("uuid_generate_v4()"),
    )
    senior_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False
    )
    guardian_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    report_type: Mapped[str] = mapped_column(
        sa.String(20), nullable=False
    )  # gp|nephro|endo|cardio|emergency
    exec_summary: Mapped[str | None] = mapped_column(sa.Text)
    pdf_url: Mapped[str | None] = mapped_column(sa.Text)
    pdf_url_expires_at: Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    generation_time_ms: Mapped[int | None] = mapped_column(sa.Integer)
    safety_gatekeeper_passed: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False
    )

    senior: Mapped[AppUser] = relationship("AppUser", back_populates="doctor_reports")
