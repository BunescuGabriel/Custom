import logging
import shutil
from pathlib import Path
from time import perf_counter

from mutagen.mp3 import MP3

from src.db.models import AudioGeneration
from src.db.repositories import create_audio_generation, find_completed_audio_generation
from src.services.text_preprocessor import clean_text, make_file_stem, make_title
from src.services.tts_service import text_to_audio

logger = logging.getLogger(__name__)


def _get_audio_duration_seconds(audio_path: Path) -> float | None:
    try:
        return round(float(MP3(audio_path).info.length), 2)
    except Exception:
        return None


def _copy_cached_audio(cached_path: Path, file_stem: str) -> Path:
    destination = cached_path.parent / f"{file_stem}.mp3"
    duplicate_number = 2
    while destination.exists():
        destination = cached_path.parent / f"{file_stem}-{duplicate_number}.mp3"
        duplicate_number += 1

    shutil.copy2(cached_path, destination)
    cached_metadata_path = cached_path.with_suffix(".jsonl")
    if cached_metadata_path.is_file():
        shutil.copy2(cached_metadata_path, destination.with_suffix(".jsonl"))
    return destination


def generate_audio_record(
    *,
    text: str,
    language: str,
    voice_name: str,
    voice_id: str,
    rate_percent: int,
    pitch_hz: int,
    title: str | None = None,
) -> AudioGeneration:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        raise ValueError("Textul nu poate fi gol.")

    record_title = title.strip() if title else make_title(cleaned_text)
    if not record_title:
        record_title = make_title(cleaned_text)
    file_stem = make_file_stem(record_title)

    cached_record = find_completed_audio_generation(
        text=cleaned_text,
        voice_id=voice_id,
        rate_percent=rate_percent,
        pitch_hz=pitch_hz,
    )
    if cached_record and cached_record.file_path and Path(cached_record.file_path).exists():
        audio_path = _copy_cached_audio(Path(cached_record.file_path), file_stem)
        logger.info(
            "audio_generation_cache_hit id=%s language=%s voice_name=%s chars=%s rate=%s pitch=%s file_name=%s",
            cached_record.id,
            language,
            voice_name,
            len(cleaned_text),
            rate_percent,
            pitch_hz,
            audio_path.name,
        )
        return create_audio_generation(
            title=record_title,
            text=cleaned_text,
            language=language,
            voice_name=voice_name,
            voice_id=voice_id,
            rate_percent=rate_percent,
            pitch_hz=pitch_hz,
            file_path=str(audio_path),
            file_name=audio_path.name,
            file_size_bytes=audio_path.stat().st_size,
            duration_seconds=_get_audio_duration_seconds(audio_path),
            generation_seconds=0.0,
            status="completed",
        )

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
            file_stem=file_stem,
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
            title=record_title,
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
        title=record_title,
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
