"""Make lab_panel.panel_date nullable so rows can be inserted before PDF parsing completes.

Revision ID: 004
Revises: 003
Create Date: 2026-04-23
"""

from __future__ import annotations

from alembic import op

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # panel_date is set by the parsing worker after vision extraction.
    # During 'parsing' state the date is unknown, so NULL must be allowed.
    op.execute("ALTER TABLE lab_panel ALTER COLUMN panel_date DROP NOT NULL")


def downgrade() -> None:
    op.execute(
        "UPDATE lab_panel SET panel_date = CURRENT_DATE WHERE panel_date IS NULL"
    )
    op.execute("ALTER TABLE lab_panel ALTER COLUMN panel_date SET NOT NULL")
