import math
from pathlib import Path

from mutagen import MutagenError
from mutagen.mp3 import MP3

from src.config import MAX_AUDIO_SECONDS


def audio_duration(path: Path) -> float:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("The MP3 file is missing or empty.")
    try:
        duration = float(MP3(path).info.length)
    except (MutagenError, OSError, ValueError) as error:
        raise ValueError("The MP3 file is corrupt or cannot be read.") from error
    if not math.isfinite(duration) or not 0 < duration <= MAX_AUDIO_SECONDS:
        raise ValueError("The MP3 duration is invalid or exceeds 10 minutes.")
    return duration
