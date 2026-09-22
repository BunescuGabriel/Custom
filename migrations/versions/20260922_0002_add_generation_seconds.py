"""add generation_seconds to audio_generations

Revision ID: 20260922_0002
Revises: 20260922_0001
Create Date: 2026-09-22
"""

import sqlalchemy as sa
from alembic import op

revision = "20260922_0002"
down_revision = "20260922_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audio_generations",
        sa.Column("generation_seconds", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audio_generations", "generation_seconds")
