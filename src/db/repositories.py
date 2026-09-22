from collections.abc import Sequence

from src.db.database import get_session
from src.db.models import AudioGeneration


def create_audio_generation(**values: object) -> AudioGeneration:
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
    with get_session() as session:
        row = (
            session.query(AudioGeneration)
            .filter(
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
