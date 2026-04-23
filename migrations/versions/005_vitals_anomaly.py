"""vitals_anomaly table — anomaly rows produced by VitalsAnomalyAgent.

Consumes wearable_daily_summary (created in 003) and produces one row per
detected anomaly marker. HIGH/URGENT rows trigger Telegram alerts; all rows
are available for the daily brief.

Revision ID: 005
Revises: 004
Create Date: 2026-04-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS vitals_anomaly (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            senior_id UUID NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
            summary_date DATE NOT NULL,
            marker VARCHAR(30) NOT NULL,
            severity VARCHAR(10) NOT NULL,
            value NUMERIC(12,4) NOT NULL,
            threshold NUMERIC(12,4) NOT NULL,
            narrative TEXT NOT NULL,
            alerted_at TIMESTAMPTZ,
            briefed BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_vitals_anomaly_summary
                FOREIGN KEY (senior_id, summary_date)
                REFERENCES wearable_daily_summary(senior_id, date)
                ON DELETE CASCADE
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vitals_anomaly_senior_created "
        "ON vitals_anomaly (senior_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vitals_anomaly_briefed "
        "ON vitals_anomaly (briefed, senior_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_vitals_anomaly_summary_marker "
        "ON vitals_anomaly (senior_id, summary_date, marker)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_vitals_anomaly_summary_marker")
    op.execute("DROP INDEX IF EXISTS ix_vitals_anomaly_briefed")
    op.execute("DROP INDEX IF EXISTS ix_vitals_anomaly_senior_created")
    op.execute("DROP TABLE IF EXISTS vitals_anomaly")
