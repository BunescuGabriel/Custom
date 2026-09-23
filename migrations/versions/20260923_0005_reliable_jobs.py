"""Persist jobs, artifact provenance and portable media paths."""

import sqlalchemy as sa
from alembic import op

revision = "20260923_0005"
down_revision = "20260922_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audio_generations",
        sa.Column("cache_hit", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column("video_generations", sa.Column("subtitle_quality", sa.String(32), nullable=True))
    op.add_column(
        "video_generations",
        sa.Column("intro_seconds", sa.Float(), nullable=False, server_default="3"),
    )
    op.execute("UPDATE video_generations SET intro_seconds = 0.05")
    op.add_column(
        "video_generations",
        sa.Column("crop_position", sa.String(16), nullable=False, server_default="center"),
    )
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("parameters", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("stage", sa.String(200), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column(
            "audio_generation_id",
            sa.Integer(),
            sa.ForeignKey("audio_generations.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "video_generation_id",
            sa.Integer(),
            sa.ForeignKey("video_generations.id", ondelete="SET NULL"),
        ),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    connection = op.get_bind()
    for table, columns in (
        ("audio_generations", ("file_path",)),
        ("video_generations", ("file_path", "background_path", "subtitle_path")),
    ):
        for column in columns:
            rows = connection.execute(sa.text(f"SELECT id, {column} FROM {table}")).all()
            for row_id, value in rows:
                normalized = (value or "").replace("\\", "/")
                if "/media/" in normalized:
                    connection.execute(
                        sa.text(f"UPDATE {table} SET {column} = :path WHERE id = :id"),
                        {"path": normalized.rsplit("/media/", 1)[1], "id": row_id},
                    )


def downgrade() -> None:
    op.drop_table("generation_jobs")
    for column in ("crop_position", "intro_seconds", "subtitle_quality"):
        op.drop_column("video_generations", column)
    op.drop_column("audio_generations", "cache_hit")
