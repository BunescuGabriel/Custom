"""create audio_generations table

Revision ID: 20260922_0001
Revises:
Create Date: 2026-09-22
"""

import sqlalchemy as sa
from alembic import op

revision = "20260922_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audio_generations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=64), nullable=False),
        sa.Column("voice_name", sa.String(length=64), nullable=False),
        sa.Column("voice_id", sa.String(length=120), nullable=False),
        sa.Column("rate_percent", sa.Integer(), nullable=False),
        sa.Column("pitch_hz", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_audio_generations_id"),
        "audio_generations",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audio_generations_id"), table_name="audio_generations")
    op.drop_table("audio_generations")
