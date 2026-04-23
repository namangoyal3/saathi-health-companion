"""Initial schema — all 10 tables, pgcrypto + uuid-ossp extensions.

Revision ID: 001
Revises:
Create Date: 2026-04-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Extensions must exist before uuid_generate_v4() server defaults work.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"")

    op.create_table(
        "app_user",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(255)),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("telegram_chat_id", sa.String(50)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "care_relationship",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guardian_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_label", sa.String(50), nullable=False),
        sa.Column("consent_matrix", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "medication",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("dose_mg", sa.Numeric(8, 2)),
        sa.Column("frequency_rrule", sa.Text),
        sa.Column("route", sa.String(20), nullable=False, server_default="oral"),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("prescriber", sa.Text),
        sa.Column("notes", JSONB),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "med_reminder_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("medication_id", UUID(as_uuid=True), sa.ForeignKey("medication.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scheduled_for", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("event", sa.String(30)),
        sa.Column("event_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("ivr_call_id", UUID(as_uuid=True)),
    )
    op.create_index(
        "ix_med_reminder_event_senior_scheduled",
        "med_reminder_event",
        ["senior_id", sa.text("scheduled_for DESC")],
    )

    op.create_table(
        "lab_panel",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("panel_date", sa.Date, nullable=False),
        sa.Column("lab_chain", sa.String(50)),
        sa.Column("pdf_path", sa.Text),
        sa.Column("parsed_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("mean_confidence", sa.Numeric(4, 3)),
        sa.Column("extraction_method", sa.String(30)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "lab_biomarker",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("lab_panel_id", UUID(as_uuid=True), sa.ForeignKey("lab_panel.id", ondelete="CASCADE"), nullable=False),
        sa.Column("biomarker", sa.String(100), nullable=False),
        sa.Column("value", sa.Numeric(12, 4)),
        sa.Column("value_text", sa.Text),
        sa.Column("unit", sa.String(30)),
        sa.Column("reference_range", sa.String(50)),
        sa.Column("confidence", sa.Numeric(4, 3)),
    )
    op.create_index(
        "ix_lab_biomarker_panel_biomarker",
        "lab_biomarker",
        ["lab_panel_id", "biomarker"],
    )

    op.create_table(
        "ivr_call_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("call_sid", sa.String(100)),
        sa.Column("flow", sa.String(5)),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("dtmf_responses", JSONB),
        sa.Column("transcript", sa.Text),
        sa.Column("duration_seconds", sa.Integer),
        sa.Column("attempt_number", sa.Integer, nullable=False, server_default="1"),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "telegram_inbound",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_message_id", sa.BigInteger),
        sa.Column("raw_text", sa.Text),
        sa.Column("message_type", sa.String(20), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="telegram"),
        sa.Column("intent", sa.String(50)),
        sa.Column("parsed_symptom", sa.Text),
        sa.Column("received_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "agent_flag",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("flag_type", sa.String(30), nullable=False),
        sa.Column("finding", sa.Text, nullable=False),
        sa.Column("drugs_involved", JSONB),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_agent_flag_senior_created",
        "agent_flag",
        ["senior_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "daily_summary",
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("brief_text", sa.Text),
        sa.Column("adherence_pct", sa.Numeric(5, 2)),
        sa.Column("flags_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("data_sources", JSONB),
        sa.Column("word_count", sa.Integer),
        sa.Column("generated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "doctor_report",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guardian_id", UUID(as_uuid=True)),
        sa.Column("report_type", sa.String(20), nullable=False),
        sa.Column("exec_summary", sa.Text),
        sa.Column("pdf_url", sa.Text),
        sa.Column("pdf_url_expires_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("generation_time_ms", sa.Integer),
        sa.Column("safety_gatekeeper_passed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("doctor_report")
    op.drop_table("daily_summary")
    op.drop_index("ix_agent_flag_senior_created", table_name="agent_flag")
    op.drop_table("agent_flag")
    op.drop_table("telegram_inbound")
    op.drop_table("ivr_call_log")
    op.drop_index("ix_lab_biomarker_panel_biomarker", table_name="lab_biomarker")
    op.drop_table("lab_biomarker")
    op.drop_table("lab_panel")
    op.drop_index("ix_med_reminder_event_senior_scheduled", table_name="med_reminder_event")
    op.drop_table("med_reminder_event")
    op.drop_table("medication")
    op.drop_table("care_relationship")
    op.drop_table("app_user")
