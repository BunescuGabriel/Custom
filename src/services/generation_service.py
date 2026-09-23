import logging
from time import perf_counter

from src.db.models import AudioGeneration
from src.db.repositories import (
    create_audio_generation,
    find_completed_audio_generations,
    update_record,
)
from src.services.audio_validation import audio_duration
from src.services.form_service import validate_request
from src.services.operations import GenerationCancelled, OperationControl, describe_error
from src.services.storage import media_reference, resolve_media_path, safe_unlink
from src.services.text_preprocessor import clean_text, make_file_stem, make_title
from src.services.tts_service import text_to_audio

logger = logging.getLogger(__name__)


def generate_audio_record(
    *,
    text: str,
    language: str,
    voice_name: str,
    voice_id: str,
    rate_percent: int,
    pitch_hz: int,
    title: str | None = None,
    control: OperationControl | None = None,
    force_synthesis: bool = False,
) -> AudioGeneration:
    parameters = dict(
        text=clean_text(text),
        language=language,
        voice_name=voice_name,
        voice_id=voice_id,
        rate_percent=rate_percent,
        pitch_hz=pitch_hz,
        title=(title or "").strip() or make_title(text),
    )
    validate_request(parameters)
    control = control or OperationControl()
    control.check()
    record = create_audio_generation(**parameters, status="pending")
    started = perf_counter()
    audio_path = None
    owns_artifact = False
    cache_hit = False
    try:
        control.record("audio", record.id)
        control.report("Verificare cache audio")
        candidates = (
            []
            if force_synthesis
            else find_completed_audio_generations(
                text=parameters["text"],
                voice_id=voice_id,
                rate_percent=rate_percent,
                pitch_hz=pitch_hz,
            )
        )
        for candidate in candidates:
            control.check()
            try:
                candidate_path = resolve_media_path(candidate.file_path)
                duration = audio_duration(candidate_path)
            except (ValueError, OSError):
                logger.warning("audio_cache_invalid id=%s", candidate.id)
                update_record(AudioGeneration, candidate.id, status="unavailable")
                continue
            audio_path = candidate_path
            cache_hit = True
            break
        if audio_path is None:
            audio_path = text_to_audio(
                parameters["text"],
                voice_id,
                rate_percent,
                pitch_hz,
                make_file_stem(parameters["title"]),
                control,
            )
            owns_artifact = True
            duration = audio_duration(audio_path)
        control.check()
        return update_record(
            AudioGeneration,
            record.id,
            file_path=media_reference(audio_path),
            file_name=make_file_stem(parameters["title"]) + ".mp3",
            file_size_bytes=audio_path.stat().st_size,
            duration_seconds=duration,
            generation_seconds=round(perf_counter() - started, 2),
            status="completed",
            cache_hit=cache_hit,
        )
    except Exception as error:
        if owns_artifact and audio_path:
            safe_unlink(audio_path, audio_path.with_suffix(".jsonl"))
        message = describe_error(error)
        try:
            update_record(
                AudioGeneration,
                record.id,
                status="cancelled" if isinstance(error, GenerationCancelled) else "failed",
                error_message=message,
                generation_seconds=round(perf_counter() - started, 2),
            )
        except Exception:
            logger.exception("audio_failure_record_unsaved id=%s", record.id)
        raise
