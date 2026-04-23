"""bot_conv_memory + bot_link_code tables.

bot_conv_memory: rolling per-user chat history (last 10 turns) used by
handle_ai_message to prepend context to every LLM call. Without this the
assistant has no memory of "you mentioned dizziness last week".

bot_link_code: short-lived code used by /link_guardian. The senior runs
/link_guardian, receives a 6-digit code, the guardian runs /link_senior <code>
in their own chat — we then set bot_profile.family_chat_id to wire alerts.

Revision ID: 006
Revises: 005
Create Date: 2026-04-23
"""

from collections.abc import Sequence

from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS bot_conv_memory (
            id BIGSERIAL PRIMARY KEY,
            chat_id BIGINT NOT NULL,
            role VARCHAR(16) NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bot_conv_memory_chat_created "
        "ON bot_conv_memory (chat_id, created_at DESC)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS bot_link_code (
            code VARCHAR(12) PRIMARY KEY,
            senior_chat_id BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 minutes'),
            consumed_at TIMESTAMPTZ
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_bot_link_code_senior "
        "ON bot_link_code (senior_chat_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_bot_link_code_senior")
    op.execute("DROP TABLE IF EXISTS bot_link_code")
    op.execute("DROP INDEX IF EXISTS ix_bot_conv_memory_chat_created")
    op.execute("DROP TABLE IF EXISTS bot_conv_memory")
