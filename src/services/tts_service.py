import asyncio
import logging
import random
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import edge_tts
from aiohttp import ClientError, ClientResponseError
from edge_tts.exceptions import NoAudioReceived, WebSocketError

from src.config import AUDIO_DIR, TTS_MAX_ATTEMPTS, TTS_RETRY_DELAY_SECONDS, TTS_TIMEOUT_SECONDS
from src.services.operations import OperationControl
from src.services.storage import safe_unlink, unique_path
from src.services.text_preprocessor import clean_text

logger = logging.getLogger(__name__)


def _retry_delay(error: Exception, attempt: int) -> float | None:
    if isinstance(error, ClientResponseError):
        if error.status not in {408, 429} and error.status < 500:
            return None
        retry_after = (error.headers or {}).get("Retry-After")
        if retry_after:
            try:
                return max(0.0, float(retry_after))
            except ValueError:
                try:
                    return max(
                        0.0,
                        (parsedate_to_datetime(retry_after) - datetime.now(UTC)).total_seconds(),
                    )
                except (TypeError, ValueError):
                    pass
    return min(16, TTS_RETRY_DELAY_SECONDS * 2 ** (attempt - 1)) + random.uniform(0, 0.5)


async def _save_audio(
    text: str, voice: str, rate: str, pitch: str, output_path: Path, control: OperationControl
) -> None:
    metadata_path = output_path.with_suffix(".jsonl")
    for attempt in range(1, TTS_MAX_ATTEMPTS + 1):
        control.report(f"Sinteză vocală: încercarea {attempt}/{TTS_MAX_ATTEMPTS}")
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
            delay = _retry_delay(error, attempt)
            if attempt == TTS_MAX_ATTEMPTS or delay is None:
                raise
            safe_unlink(output_path, metadata_path)
            logger.warning(
                "audio_retry attempt=%s error_type=%s delay=%s",
                attempt,
                type(error).__name__,
                delay,
            )
            control.report(f"Serviciul de voce reîncearcă în {delay:.1f} secunde")
            await asyncio.sleep(delay)


async def _run_synthesis(text, voice, rate, pitch, path, control):
    task = asyncio.create_task(_save_audio(text, voice, rate, pitch, path, control))
    try:
        async with asyncio.timeout(TTS_TIMEOUT_SECONDS):
            while not task.done():
                control.check()
                await asyncio.wait({task}, timeout=0.25)
            await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


def _make_output_path(file_stem: str | None) -> Path:
    return unique_path(AUDIO_DIR, file_stem or "audio", ".mp3")


def text_to_audio(
    text: str,
    voice: str,
    rate_percent: int = 0,
    pitch_hz: int = 0,
    file_stem: str | None = None,
    control: OperationControl | None = None,
) -> Path:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        raise ValueError("Textul nu poate fi gol.")
    output_path = _make_output_path(file_stem)
    temporary_path = output_path.with_name(output_path.stem + ".part.mp3")
    control = control or OperationControl()
    try:
        asyncio.run(
            _run_synthesis(
                cleaned_text,
                voice,
                f"{rate_percent:+d}%",
                f"{pitch_hz:+d}Hz",
                temporary_path,
                control,
            )
        )
        control.check()
        temporary_path.with_suffix(".jsonl").replace(output_path.with_suffix(".jsonl"))
        temporary_path.replace(output_path)
        return output_path
    except BaseException:
        safe_unlink(
            temporary_path,
            temporary_path.with_suffix(".jsonl"),
            output_path,
            output_path.with_suffix(".jsonl"),
        )
        raise
