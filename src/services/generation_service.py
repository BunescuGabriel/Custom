import logging
from pathlib import Path
from time import perf_counter

from mutagen.mp3 import MP3

from src.db.models import AudioGeneration
from src.db.repositories import create_audio_generation, find_completed_audio_generation
from src.services.text_preprocessor import clean_text, make_title
from src.services.tts_service import text_to_audio

logger = logging.getLogger(__name__)


def _get_audio_duration_seconds(audio_path: Path) -> float | None:
    try:
        return round(float(MP3(audio_path).info.length), 2)
    except Exception:
        return None


def generate_audio_record(
    *,
    text: str,
    language: str,
    voice_name: str,
    voice_id: str,
    rate_percent: int,
    pitch_hz: int,
) -> AudioGeneration:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        raise ValueError("Textul nu poate fi gol.")

    cached_record = find_completed_audio_generation(
        text=cleaned_text,
        voice_id=voice_id,
        rate_percent=rate_percent,
        pitch_hz=pitch_hz,
    )
    if cached_record and cached_record.file_path and Path(cached_record.file_path).exists():
        logger.info(
            "audio_generation_cache_hit id=%s language=%s voice_name=%s chars=%s rate=%s pitch=%s",
            cached_record.id,
            language,
            voice_name,
            len(cleaned_text),
            rate_percent,
            pitch_hz,
        )
        return cached_record

    started_at = perf_counter()
    logger.info(
        "audio_generation_started language=%s voice_name=%s voice_id=%s chars=%s rate=%s pitch=%s",
        language,
        voice_name,
        voice_id,
        len(cleaned_text),
        rate_percent,
        pitch_hz,
    )

    try:
        audio_path = text_to_audio(
            text=cleaned_text,
            voice=voice_id,
            rate_percent=rate_percent,
            pitch_hz=pitch_hz,
        )
    except Exception as error:
        generation_seconds = round(perf_counter() - started_at, 2)
        logger.exception(
            "audio_generation_failed language=%s voice_name=%s elapsed_seconds=%s",
            language,
            voice_name,
            generation_seconds,
        )
        create_audio_generation(
            title=make_title(cleaned_text),
            text=cleaned_text,
            language=language,
            voice_name=voice_name,
            voice_id=voice_id,
            rate_percent=rate_percent,
            pitch_hz=pitch_hz,
            generation_seconds=generation_seconds,
            status="failed",
            error_message=str(error),
        )
        raise

    generation_seconds = round(perf_counter() - started_at, 2)
    file_size_bytes = audio_path.stat().st_size
    duration_seconds = _get_audio_duration_seconds(audio_path)
    logger.info(
        "audio_generation_completed language=%s voice_name=%s elapsed_seconds=%s audio_duration_seconds=%s file_size_bytes=%s",
        language,
        voice_name,
        generation_seconds,
        duration_seconds,
        file_size_bytes,
    )

    return create_audio_generation(
        title=make_title(cleaned_text),
        text=cleaned_text,
        language=language,
        voice_name=voice_name,
        voice_id=voice_id,
        rate_percent=rate_percent,
        pitch_hz=pitch_hz,
        file_path=str(audio_path),
        file_name=audio_path.name,
        file_size_bytes=file_size_bytes,
        duration_seconds=duration_seconds,
        generation_seconds=generation_seconds,
        status="completed",
    )
