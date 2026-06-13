"""per-channel tone of voice

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean slate: existing rows are not channel-tagged (design decision).
    op.execute("DELETE FROM tone_of_voices")
    with op.batch_alter_table("tone_of_voices") as batch:
        batch.add_column(sa.Column("channel", sa.String(16), nullable=False, server_default="linkedin"))
        batch.create_unique_constraint("uq_tov_user_channel", ["user_id", "channel"])
        batch.create_index("ix_tone_of_voices_channel", ["channel"])
    # Drop the temporary server_default now that the table is empty.
    with op.batch_alter_table("tone_of_voices") as batch:
        batch.alter_column("channel", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("tone_of_voices") as batch:
        batch.drop_index("ix_tone_of_voices_channel")
        batch.drop_constraint("uq_tov_user_channel", type_="unique")
        batch.drop_column("channel")
