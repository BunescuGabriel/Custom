import math
from pathlib import Path

from mutagen import MutagenError
from mutagen.mp3 import MP3

from src.config import MAX_AUDIO_SECONDS


def audio_duration(path: Path) -> float:
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("Fișierul MP3 lipsește sau este gol.")
    try:
        duration = float(MP3(path).info.length)
    except (MutagenError, OSError, ValueError) as error:
        raise ValueError("Fișierul MP3 este deteriorat sau nu poate fi citit.") from error
    if not math.isfinite(duration) or not 0 < duration <= MAX_AUDIO_SECONDS:
        raise ValueError("Durata MP3 nu este validă sau depășește 10 minute.")
    return duration
