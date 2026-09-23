"""create video_generations table

Revision ID: 20260922_0004
Revises: 20260922_0003
Create Date: 2026-09-22
"""

import sqlalchemy as sa
from alembic import op

revision = "20260922_0004"
down_revision = "20260922_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_generations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("audio_generation_id", sa.Integer(), nullable=False),
        sa.Column("background_path", sa.String(length=500), nullable=False),
        sa.Column("subtitle_path", sa.String(length=500), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("generation_seconds", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["audio_generation_id"], ["audio_generations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_video_generations_id"), "video_generations", ["id"], unique=False)
    op.create_index(
        op.f("ix_video_generations_audio_generation_id"),
        "video_generations",
        ["audio_generation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_video_generations_audio_generation_id", table_name="video_generations")
    op.drop_index("ix_video_generations_id", table_name="video_generations")
    op.drop_table("video_generations")
