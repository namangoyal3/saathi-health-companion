"""Bot-layer tables: bot_profile, bot_medication, bot_med_event, bot_snooze_count.

Revision ID: 002
Revises: 001
Create Date: 2026-04-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bot_profile",
        sa.Column("chat_id", sa.BigInteger, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, server_default=""),
        sa.Column("language", sa.String(10), nullable=False, server_default="hi"),
        sa.Column("conditions", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("family_chat_id", sa.BigInteger),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "bot_medication",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("chat_id", sa.BigInteger, sa.ForeignKey("bot_profile.chat_id", ondelete="CASCADE"), nullable=False),
        sa.Column("drug_name", sa.Text, nullable=False),
        sa.Column("dose", sa.Text),
        sa.Column("frequency", sa.Text),
        sa.Column("timings", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bot_medication_chat_id", "bot_medication", ["chat_id"])

    op.create_table(
        "bot_med_event",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("medication_id", UUID(as_uuid=True)),
        sa.Column("drug_name", sa.Text, nullable=False, server_default=""),
        sa.Column("event", sa.Text, nullable=False),
        sa.Column("reminder_id", sa.Text),
        sa.Column("scheduled_for", sa.Text),
        sa.Column("event_date", sa.Date, nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bot_med_event_chat_date", "bot_med_event", ["chat_id", "event_date"])

    op.create_table(
        "bot_snooze_count",
        sa.Column("reminder_id", sa.Text, primary_key=True),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bot_snooze_count")
    op.drop_index("ix_bot_med_event_chat_date", "bot_med_event")
    op.drop_table("bot_med_event")
    op.drop_index("ix_bot_medication_chat_id", "bot_medication")
    op.drop_table("bot_medication")
    op.drop_table("bot_profile")
