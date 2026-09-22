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
