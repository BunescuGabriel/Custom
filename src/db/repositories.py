from collections.abc import Sequence
from hashlib import sha256

from sqlalchemy.orm import selectinload

from src.db.database import get_session
from src.db.models import AudioGeneration, GenerationJob, VideoGeneration


def _make_content_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def create_audio_generation(**values: object) -> AudioGeneration:
    text = values.get("text")
    if not isinstance(text, str):
        raise TypeError("Audio generation text must be a string.")

    values["content_hash"] = _make_content_hash(text)
    with get_session() as session:
        generation = AudioGeneration(**values)
        session.add(generation)
        session.flush()
        session.refresh(generation)
        session.expunge(generation)
        return generation


def find_completed_audio_generations(
    *,
    text: str,
    voice_id: str,
    rate_percent: int,
    pitch_hz: int,
) -> Sequence[AudioGeneration]:
    content_hash = _make_content_hash(text)
    with get_session() as session:
        rows = (
            session.query(AudioGeneration)
            .filter(
                AudioGeneration.content_hash == content_hash,
                AudioGeneration.text == text,
                AudioGeneration.voice_id == voice_id,
                AudioGeneration.rate_percent == rate_percent,
                AudioGeneration.pitch_hz == pitch_hz,
                AudioGeneration.status == "completed",
                AudioGeneration.file_path.isnot(None),
            )
            .order_by(AudioGeneration.created_at.desc(), AudioGeneration.id.desc())
            .all()
        )
        session.expunge_all()
        return rows


def list_audio_generations(
    limit: int = 50, offset: int = 0, search: str = "", status: str = ""
) -> Sequence[AudioGeneration]:
    with get_session() as session:
        rows = (
            session.query(AudioGeneration)
            .filter(AudioGeneration.title.contains(search, autoescape=True))
            .filter(AudioGeneration.status == status if status else True)
            .order_by(AudioGeneration.created_at.desc(), AudioGeneration.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        for row in rows:
            session.expunge(row)
        return rows


def create_video_generation(**values: object) -> VideoGeneration:
    with get_session() as session:
        generation = VideoGeneration(**values)
        session.add(generation)
        session.flush()
        session.refresh(generation)
        session.expunge(generation)
        return generation


def list_video_generations(
    limit: int = 50, offset: int = 0, search: str = "", status: str = ""
) -> Sequence[VideoGeneration]:
    with get_session() as session:
        rows = (
            session.query(VideoGeneration)
            .outerjoin(AudioGeneration)
            .filter(AudioGeneration.title.contains(search, autoescape=True) if search else True)
            .filter(VideoGeneration.status == status if status else True)
            .options(selectinload(VideoGeneration.audio_generation))
            .order_by(VideoGeneration.created_at.desc(), VideoGeneration.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        session.expunge_all()
        return rows


def get_record(model, record_id):
    with get_session() as session:
        row = session.get(model, record_id)
        if isinstance(row, VideoGeneration):
            _ = row.audio_generation
        session.expunge_all()
        return row


def update_record(model, record_id, **values):
    with get_session() as session:
        row = session.get(model, record_id)
        if row is None:
            raise ValueError("Înregistrarea nu mai există.")
        for key, value in values.items():
            setattr(row, key, value)
        session.flush()
        session.refresh(row)
        session.expunge(row)
        return row


def create_job(**values) -> GenerationJob:
    with get_session() as session:
        row = GenerationJob(**values)
        session.add(row)
        session.flush()
        session.expunge(row)
        return row


def list_jobs(limit: int = 20) -> Sequence[GenerationJob]:
    with get_session() as session:
        rows = (
            session.query(GenerationJob)
            .order_by(GenerationJob.created_at.desc())
            .limit(limit)
            .all()
        )
        session.expunge_all()
        return rows


def has_active_jobs() -> bool:
    with get_session() as session:
        return (
            session.query(GenerationJob.id)
            .filter(GenerationJob.status.in_(("queued", "running")))
            .first()
            is not None
        )
