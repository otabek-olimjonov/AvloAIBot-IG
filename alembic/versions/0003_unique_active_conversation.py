"""unique active conversation per user

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deduplicate: keep only the most-recent active conversation per user,
    # end any earlier duplicates that snuck in via race conditions.
    op.execute("""
        UPDATE conversations
        SET status = 'ended', ended_at = NOW()
        WHERE status = 'active'
          AND id NOT IN (
              SELECT DISTINCT ON (instagram_user_id) id
              FROM conversations
              WHERE status = 'active'
              ORDER BY instagram_user_id, started_at DESC
          )
    """)

    # Partial unique index: at most one active conversation per Instagram user.
    op.create_index(
        "uix_conversations_active_user",
        "conversations",
        ["instagram_user_id"],
        unique=True,
        postgresql_where="status = 'active'",
    )


def downgrade() -> None:
    op.drop_index("uix_conversations_active_user", table_name="conversations")
