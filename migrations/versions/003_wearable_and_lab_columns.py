"""Migration 003: wearable_daily_summary table + lab_panel columns.

Revision ID: 003
Revises: 002
Create Date: 2026-04-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Wearable daily summary table
    op.create_table(
        "wearable_daily_summary",
        sa.Column("senior_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("steps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_heart_rate", sa.Integer),
        sa.Column("sleep_minutes", sa.Integer),
        sa.Column("sleep_efficiency_pct", sa.Integer),
        sa.Column("sleep_score", sa.Integer),
        sa.Column("avg_spo2_pct", sa.Integer),
        sa.Column("avg_skin_temp_c", sa.Numeric(5, 2)),
        sa.Column("hrv_rmssd", sa.Integer),
        sa.Column("stress_score", sa.Integer),
        sa.Column("exercise_minutes", sa.Integer),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("senior_id", "date"),
    )

    # Add missing columns to lab_panel (status, r2_key, filename, collection_date, lab_chain, error)
    op.add_column("lab_panel", sa.Column("status", sa.String(30), nullable=False, server_default="pending"))
    op.add_column("lab_panel", sa.Column("r2_key", sa.Text))
    op.add_column("lab_panel", sa.Column("filename", sa.Text))
    op.add_column("lab_panel", sa.Column("collection_date", sa.Date))
    op.add_column("lab_panel", sa.Column("lab_chain", sa.String(50)))
    op.add_column("lab_panel", sa.Column("error", sa.Text))


def downgrade() -> None:
    op.drop_column("lab_panel", "error")
    op.drop_column("lab_panel", "lab_chain")
    op.drop_column("lab_panel", "collection_date")
    op.drop_column("lab_panel", "filename")
    op.drop_column("lab_panel", "r2_key")
    op.drop_column("lab_panel", "status")
    op.drop_table("wearable_daily_summary")
