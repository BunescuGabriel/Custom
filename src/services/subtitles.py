import html
import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path

from src.config import SUBTITLE_DIR, VIDEO_HEIGHT, VIDEO_WIDTH
from src.services.storage import safe_unlink, unique_path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubtitleCue:
    start_seconds: float
    end_seconds: float
    text: str


def _normalized_words(text: str) -> str:
    return "".join(re.findall(r"\w+", html.unescape(text).casefold()))


def load_word_cues(metadata_path: Path, text: str, duration: float) -> list[SubtitleCue]:
    try:
        if not metadata_path.is_file() or metadata_path.stat().st_size > 5 * 1024 * 1024:
            return []
        words = []
        previous_end = 0.0
        for line in metadata_path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("Metadata must be an object")
            if item.get("type") != "WordBoundary":
                continue
            word = item.get("text")
            if not isinstance(word, str) or not word.strip():
                raise ValueError("Invalid word")
            if any(
                isinstance(item.get(key), bool) or not isinstance(item.get(key), (int, float))
                for key in ("offset", "duration")
            ):
                raise ValueError("Invalid timestamp type")
            start = item["offset"] / 10_000_000
            end = start + item["duration"] / 10_000_000
            if (
                not all(math.isfinite(value) for value in (start, end))
                or start < 0
                or start < previous_end - 0.001
                or end <= start
                or end > duration + 0.1
            ):
                raise ValueError("Invalid timestamp range")
            words.append(SubtitleCue(start, min(end, duration), html.unescape(word)))
            previous_end = end
        if not words or _normalized_words(
            " ".join(word.text for word in words)
        ) != _normalized_words(text):
            raise ValueError("Incomplete word boundaries")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError):
        logger.warning("subtitle_metadata_invalid path=%s", metadata_path)
        return []
    cues = []
    for index in range(0, len(words), 6):
        group = words[index : index + 6]
        cues.append(
            SubtitleCue(
                group[0].start_seconds, group[-1].end_seconds, " ".join(word.text for word in group)
            )
        )
    return cues


def fallback_cues(text: str, duration: float) -> list[SubtitleCue]:
    words = text.split()
    if not words:
        return []
    return [
        SubtitleCue(
            duration * index / len(words),
            duration * min(index + 6, len(words)) / len(words),
            " ".join(words[index : index + 6]),
        )
        for index in range(0, len(words), 6)
    ]


def _ass_timestamp(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds_part, hundredths = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds_part:02d}.{hundredths:02d}"


def _escape_ass_text(text: str) -> str:
    return text.replace("\\", "＼").replace("{", "｛").replace("}", "｝").replace("\n", r"\N")


def write_subtitles(
    audio_record, audio_path: Path, duration: float, intro: float, allow_approximate: bool
) -> tuple[Path, str]:
    cues = load_word_cues(audio_path.with_suffix(".jsonl"), audio_record.text, duration)
    quality = "provider"
    if not cues:
        if not allow_approximate:
            raise ValueError(
                "Lipsesc timpii compleți ai cuvintelor. Activează explicit subtitrările aproximative sau generează din nou audio-ul."
            )
        quality = "approximate"
        cues = fallback_cues(audio_record.text, duration)
    if not cues:
        raise ValueError("Nu există text pentru subtitrări.")
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,DejaVu Sans,62,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,90,90,300,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    for cue in cues:
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(cue.start_seconds + intro)},{_ass_timestamp(cue.end_seconds + intro)},Default,,0,0,0,,{_escape_ass_text(cue.text)}\n"
        )
    path = unique_path(SUBTITLE_DIR, "subtitles", ".ass")
    try:
        path.write_text("".join(lines), encoding="utf-8-sig")
    except OSError:
        safe_unlink(path)
        raise
    return path, quality
