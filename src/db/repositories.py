from collections.abc import Sequence
from hashlib import sha256

from src.db.database import get_session
from src.db.models import AudioGeneration


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


def find_completed_audio_generation(
    *,
    text: str,
    voice_id: str,
    rate_percent: int,
    pitch_hz: int,
) -> AudioGeneration | None:
    content_hash = _make_content_hash(text)
    with get_session() as session:
        row = (
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
            .first()
        )
        if row is None:
            return None

        session.expunge(row)
        return row


def list_audio_generations(limit: int = 50) -> Sequence[AudioGeneration]:
    with get_session() as session:
        rows = (
            session.query(AudioGeneration)
            .order_by(AudioGeneration.created_at.desc(), AudioGeneration.id.desc())
            .limit(limit)
            .all()
        )
        for row in rows:
            session.expunge(row)
        return rows
