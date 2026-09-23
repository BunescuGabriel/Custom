import asyncio
import logging
from pathlib import Path
from uuid import uuid4

import edge_tts
from aiohttp import ClientError
from edge_tts.exceptions import NoAudioReceived, WebSocketError

from src.config import AUDIO_DIR, TTS_MAX_ATTEMPTS, TTS_RETRY_DELAY_SECONDS, TTS_TIMEOUT_SECONDS
from src.services.text_preprocessor import clean_text

logger = logging.getLogger(__name__)


async def _save_audio(text: str, voice: str, rate: str, pitch: str, output_path: Path) -> None:
    metadata_path = output_path.with_suffix(".jsonl")
    for attempt in range(1, TTS_MAX_ATTEMPTS + 1):
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate=rate,
            pitch=pitch,
            boundary="WordBoundary",
        )
        try:
            await communicate.save(str(output_path), str(metadata_path))
            return
        except (NoAudioReceived, WebSocketError, ClientError, TimeoutError) as error:
            if attempt == TTS_MAX_ATTEMPTS:
                raise

            output_path.unlink(missing_ok=True)
            metadata_path.unlink(missing_ok=True)
            logger.warning(
                "audio_generation_retry attempt=%s max_attempts=%s voice=%s "
                "error_type=%s retry_in_seconds=%s",
                attempt,
                TTS_MAX_ATTEMPTS,
                voice,
                type(error).__name__,
                TTS_RETRY_DELAY_SECONDS,
            )
            await asyncio.sleep(TTS_RETRY_DELAY_SECONDS)


def _make_output_path(file_stem: str | None) -> Path:
    base_name = file_stem or f"audio-{uuid4().hex}"
    output_path = AUDIO_DIR / f"{Path(base_name).name}.mp3"
    duplicate_number = 2
    while output_path.exists():
        output_path = AUDIO_DIR / f"{Path(base_name).name}-{duplicate_number}.mp3"
        duplicate_number += 1
    return output_path


def text_to_audio(
    text: str,
    voice: str,
    rate_percent: int = 0,
    pitch_hz: int = 0,
    file_stem: str | None = None,
) -> Path:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        raise ValueError("Textul nu poate fi gol.")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    output_path = _make_output_path(file_stem)
    rate = f"{rate_percent:+d}%"
    pitch = f"{pitch_hz:+d}Hz"

    try:
        asyncio.run(
            asyncio.wait_for(
                _save_audio(cleaned_text, voice, rate, pitch, output_path),
                timeout=TTS_TIMEOUT_SECONDS,
            )
        )
    except Exception:
        output_path.unlink(missing_ok=True)
        output_path.with_suffix(".jsonl").unlink(missing_ok=True)
        raise

    return output_path
