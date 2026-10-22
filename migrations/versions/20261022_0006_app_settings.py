"""Persist editable application settings."""

import sqlalchemy as sa
from alembic import op

revision = "20261022_0006"
down_revision = "20260923_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_width", sa.Integer(), nullable=False),
        sa.Column("video_height", sa.Integer(), nullable=False),
        sa.Column("video_fps", sa.Integer(), nullable=False),
        sa.Column("title_duration_seconds", sa.Float(), nullable=False),
        sa.Column("default_rate_percent", sa.Integer(), nullable=False),
        sa.Column("default_pitch_hz", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("app_settings")
