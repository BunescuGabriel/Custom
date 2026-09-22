import asyncio
import logging
from pathlib import Path
from uuid import uuid4

import edge_tts

from src.config import AUDIO_DIR, TTS_TIMEOUT_SECONDS
from src.services.text_preprocessor import clean_text

logger = logging.getLogger(__name__)


async def _save_audio(text: str, voice: str, rate: str, pitch: str, output_path: Path) -> None:
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )
    await communicate.save(str(output_path))


def text_to_audio(text: str, voice: str, rate_percent: int = 0, pitch_hz: int = 0) -> Path:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        raise ValueError("Textul nu poate fi gol.")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    output_path = AUDIO_DIR / f"audio-{uuid4().hex}.mp3"
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
        if output_path.exists() and output_path.stat().st_size == 0:
            output_path.unlink()
            logger.info("removed_empty_audio_file path=%s", output_path)
        raise

    return output_path
