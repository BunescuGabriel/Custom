"""add audio generation cache index

Revision ID: 20260922_0003
Revises: 20260922_0002
Create Date: 2026-09-22
"""

from hashlib import sha256

import sqlalchemy as sa
from alembic import op

revision = "20260922_0003"
down_revision = "20260922_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audio_generations",
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, text FROM audio_generations")).mappings()
    for row in rows:
        content_hash = sha256(row["text"].encode("utf-8")).hexdigest()
        connection.execute(
            sa.text("UPDATE audio_generations SET content_hash = :content_hash WHERE id = :id"),
            {"content_hash": content_hash, "id": row["id"]},
        )

    with op.batch_alter_table("audio_generations") as batch_op:
        batch_op.alter_column(
            "content_hash",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_index(
            "ix_audio_generations_cache_lookup",
            [
                "content_hash",
                "voice_id",
                "rate_percent",
                "pitch_hz",
                "status",
                "created_at",
                "id",
            ],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("audio_generations") as batch_op:
        batch_op.drop_index("ix_audio_generations_cache_lookup")
        batch_op.drop_column("content_hash")
