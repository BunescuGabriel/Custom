from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.database import Base


class AudioGeneration(Base):
    __tablename__ = "audio_generations"
    __table_args__ = (
        Index(
            "ix_audio_generations_cache_lookup",
            "content_hash",
            "voice_id",
            "rate_percent",
            "pitch_hz",
            "status",
            "created_at",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str] = mapped_column(String(64), nullable=False)
    voice_name: Mapped[str] = mapped_column(String(64), nullable=False)
    voice_id: Mapped[str] = mapped_column(String(120), nullable=False)
    rate_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pitch_hz: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    video_generations: Mapped[list["VideoGeneration"]] = relationship(
        back_populates="audio_generation"
    )


class VideoGeneration(Base):
    __tablename__ = "video_generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    audio_generation_id: Mapped[int] = mapped_column(
        ForeignKey("audio_generations.id"), nullable=False, index=True
    )
    background_path: Mapped[str] = mapped_column(String(500), nullable=False)
    subtitle_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    subtitle_quality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    intro_seconds: Mapped[float] = mapped_column(
        Float, nullable=False, default=3.0, server_default="3"
    )
    crop_position: Mapped[str] = mapped_column(
        String(16), nullable=False, default="center", server_default="center"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    audio_generation: Mapped[AudioGeneration] = relationship(back_populates="video_generations")


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parameters: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    stage: Mapped[str] = mapped_column(String(200), nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    audio_generation_id: Mapped[int | None] = mapped_column(
        ForeignKey("audio_generations.id", ondelete="SET NULL")
    )
    video_generation_id: Mapped[int | None] = mapped_column(
        ForeignKey("video_generations.id", ondelete="SET NULL")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
