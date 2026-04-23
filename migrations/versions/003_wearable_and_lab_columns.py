"""Migration 003: wearable_daily_summary table + lab_panel columns.

Revision ID: 003
Revises: 002
Create Date: 2026-04-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Wearable daily summary table — idempotent
    op.execute("""
        CREATE TABLE IF NOT EXISTS wearable_daily_summary (
            senior_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
            date DATE NOT NULL,
            steps INTEGER NOT NULL DEFAULT 0,
            avg_heart_rate INTEGER,
            sleep_minutes INTEGER,
            sleep_efficiency_pct INTEGER,
            sleep_score INTEGER,
            avg_spo2_pct INTEGER,
            avg_skin_temp_c NUMERIC(5,2),
            hrv_rmssd INTEGER,
            stress_score INTEGER,
            exercise_minutes INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (senior_id, date)
        )
    """)

    # Add missing columns to lab_panel — each uses IF NOT EXISTS to be idempotent
    for col_ddl in [
        "ALTER TABLE lab_panel ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'pending'",
        "ALTER TABLE lab_panel ADD COLUMN IF NOT EXISTS r2_key TEXT",
        "ALTER TABLE lab_panel ADD COLUMN IF NOT EXISTS filename TEXT",
        "ALTER TABLE lab_panel ADD COLUMN IF NOT EXISTS collection_date DATE",
        "ALTER TABLE lab_panel ADD COLUMN IF NOT EXISTS lab_chain VARCHAR(50)",
        "ALTER TABLE lab_panel ADD COLUMN IF NOT EXISTS error TEXT",
    ]:
        op.execute(col_ddl)


def downgrade() -> None:
    op.drop_column("lab_panel", "error")
    op.drop_column("lab_panel", "lab_chain")
    op.drop_column("lab_panel", "collection_date")
    op.drop_column("lab_panel", "filename")
    op.drop_column("lab_panel", "r2_key")
    op.drop_column("lab_panel", "status")
    op.drop_table("wearable_daily_summary")
