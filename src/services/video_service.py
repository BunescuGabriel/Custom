import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from mutagen.mp3 import MP3

from src.config import (
    SUBTITLE_DIR,
    VIDEO_DIR,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_RENDER_TIMEOUT_SECONDS,
    VIDEO_TITLE_DURATION_SECONDS,
    VIDEO_TITLE_PREVIEW_SECONDS,
    VIDEO_WIDTH,
)
from src.db.models import AudioGeneration, VideoGeneration
from src.db.repositories import create_video_generation
from src.services.title_overlay_service import TitleOverlayError, create_title_overlay

logger = logging.getLogger(__name__)


class VideoServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class SubtitleCue:
    start_seconds: float
    end_seconds: float
    text: str


def is_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _get_ffmpeg_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise VideoServiceError(
            "FFmpeg nu este instalat sau nu este disponibil in PATH. "
            "Instaleaza FFmpeg, redeschide terminalul si incearca din nou."
        )
    return executable


def _audio_duration_seconds(audio_path: Path) -> float:
    try:
        duration = float(MP3(audio_path).info.length)
    except Exception as error:
        raise VideoServiceError("Nu pot determina durata fisierului audio generat.") from error

    if duration <= 0:
        raise VideoServiceError("Fisierul audio generat nu are durata valida.")
    return duration


def _load_word_cues(metadata_path: Path) -> list[SubtitleCue]:
    if not metadata_path.is_file():
        return []

    words: list[tuple[float, float, str]] = []
    try:
        for line in metadata_path.read_text(encoding="utf-8").splitlines():
            item = json.loads(line)
            if item.get("type") != "WordBoundary":
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            start = int(item["offset"]) / 10_000_000
            end = start + int(item["duration"]) / 10_000_000
            words.append((start, end, text))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.warning("subtitle_metadata_invalid path=%s", metadata_path)
        return []

    cues: list[SubtitleCue] = []
    group: list[tuple[float, float, str]] = []
    for word in words:
        group.append(word)
        text = word[2]
        ends_sentence = text.endswith((".", "!", "?", "…"))
        if len(group) >= 6 or ends_sentence:
            cues.append(
                SubtitleCue(
                    group[0][0],
                    max(group[-1][1], group[0][0] + 0.15),
                    " ".join(item[2] for item in group),
                )
            )
            group = []
    if group:
        cues.append(
            SubtitleCue(
                group[0][0],
                max(group[-1][1], group[0][0] + 0.15),
                " ".join(item[2] for item in group),
            )
        )
    return cues


def _fallback_cues(text: str, duration_seconds: float) -> list[SubtitleCue]:
    words = text.split()
    if not words:
        return []

    word_groups = [words[index : index + 6] for index in range(0, len(words), 6)]
    total_words = len(words)
    elapsed = 0.0
    cues: list[SubtitleCue] = []
    for group in word_groups:
        cue_duration = duration_seconds * len(group) / total_words
        cues.append(
            SubtitleCue(elapsed, min(elapsed + cue_duration, duration_seconds), " ".join(group))
        )
        elapsed += cue_duration
    return cues


def _ass_timestamp(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds_part, hundredths = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds_part:02d}.{hundredths:02d}"


def _escape_ass_text(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def _write_subtitles(audio_record: AudioGeneration, duration_seconds: float) -> Path:
    audio_path = Path(audio_record.file_path or "")
    cues = _load_word_cues(audio_path.with_suffix(".jsonl"))
    if not cues:
        logger.info("subtitle_timing_fallback audio_generation_id=%s", audio_record.id)
        cues = _fallback_cues(audio_record.text, duration_seconds)
    if not cues:
        raise VideoServiceError("Nu pot crea subtitrari pentru un text gol.")

    SUBTITLE_DIR.mkdir(parents=True, exist_ok=True)
    subtitle_path = SUBTITLE_DIR / f"subtitles-{uuid4().hex}.ass"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,Arial,62,&H00FFFFFF,&H000000FF,&H00101010,&H80000000,1,0,0,0,100,100,0,0,1,3,1,2,90,90,300,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    title_end = min(VIDEO_TITLE_DURATION_SECONDS, duration_seconds)
    for cue in cues:
        if cue.end_seconds <= title_end:
            continue
        start = max(cue.start_seconds, title_end)
        end = max(cue.end_seconds, cue.start_seconds + 0.1)
        lines.append(
            f"Dialogue: 0,{_ass_timestamp(start)},{_ass_timestamp(end)},Default,,0,0,0,,{_escape_ass_text(cue.text)}\n"
        )
    subtitle_path.write_text("".join(lines), encoding="utf-8-sig")
    return subtitle_path


def _validate_background(background_path: Path) -> None:
    if not background_path.is_file():
        raise VideoServiceError("Videoclipul de fundal nu mai exista pe disc.")

    ffprobe = _get_ffmpeg_executable("ffprobe")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type,width,height",
            "-of",
            "json",
            str(background_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    try:
        streams = json.loads(result.stdout).get("streams", [])
    except json.JSONDecodeError as error:
        raise VideoServiceError("Nu pot verifica videoclipul de fundal.") from error
    if result.returncode != 0 or not streams:
        raise VideoServiceError("Fisierul selectat nu contine un stream video compatibil.")


def _ass_filter_path(subtitle_path: Path) -> str:
    return (
        subtitle_path.resolve()
        .as_posix()
        .replace("\\", "/")
        .replace(":", r"\:")
        .replace("'", r"\'")
    )


def _make_output_path(file_stem: str) -> Path:
    output_path = VIDEO_DIR / f"{Path(file_stem).name}.mp4"
    duplicate_number = 2
    while output_path.exists():
        output_path = VIDEO_DIR / f"{Path(file_stem).name}-{duplicate_number}.mp4"
        duplicate_number += 1
    return output_path


def _render_video(
    background_path: Path,
    audio_path: Path,
    subtitle_path: Path,
    title_overlay_path: Path,
    duration_seconds: float,
) -> Path:
    ffmpeg = _get_ffmpeg_executable("ffmpeg")
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    output_path = _make_output_path(audio_path.stem)
    video_filter = (
        f"[0:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1,fps={VIDEO_FPS}[background];"
        f"[3:v]scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},setsar=1,fps={VIDEO_FPS},setpts=PTS-STARTPTS[preview];"
        f"[background][preview]overlay=0:0:format=auto:"
        f"enable='between(t,0,{VIDEO_TITLE_DURATION_SECONDS})'[opening];"
        f"[2:v]format=rgba[title];"
        f"[opening][title]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2:"
        f"format=auto:enable='between(t,0,{VIDEO_TITLE_DURATION_SECONDS})',"
        f"ass='{_ass_filter_path(subtitle_path)}'[video]"
    )
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(background_path),
            "-i",
            str(audio_path),
            "-loop",
            "1",
            "-framerate",
            str(VIDEO_FPS),
            "-i",
            str(title_overlay_path),
            "-ss",
            str(VIDEO_TITLE_PREVIEW_SECONDS),
            "-i",
            str(background_path),
            "-filter_complex",
            video_filter,
            "-map",
            "[video]",
            "-map",
            "1:a:0",
            "-t",
            f"{duration_seconds:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=VIDEO_RENDER_TIMEOUT_SECONDS,
        check=False,
    )
    if result.returncode != 0 or not output_path.is_file():
        output_path.unlink(missing_ok=True)
        error_text = result.stderr.strip() or "FFmpeg nu a putut randa videoclipul."
        raise VideoServiceError(error_text[-1000:])
    return output_path


def generate_video_record(
    *, audio_record: AudioGeneration, background_path: Path
) -> VideoGeneration:
    audio_path = Path(audio_record.file_path or "")
    if audio_record.status != "completed" or not audio_path.is_file():
        raise VideoServiceError("Audio-ul necesar pentru videoclip nu este disponibil.")

    started_at = perf_counter()
    subtitle_path: Path | None = None
    title_overlay_path: Path | None = None
    output_path: Path | None = None
    try:
        _validate_background(background_path)
        duration_seconds = _audio_duration_seconds(audio_path)
        subtitle_path = _write_subtitles(audio_record, duration_seconds)
        title_overlay_path = create_title_overlay(audio_record.title)
        logger.info(
            "video_generation_started audio_generation_id=%s background=%s title_preview_seconds=%s duration_seconds=%s",
            audio_record.id,
            background_path.name,
            VIDEO_TITLE_PREVIEW_SECONDS,
            round(duration_seconds, 2),
        )
        output_path = _render_video(
            background_path,
            audio_path,
            subtitle_path,
            title_overlay_path,
            duration_seconds,
        )
        generation_seconds = round(perf_counter() - started_at, 2)
        logger.info(
            "video_generation_completed audio_generation_id=%s elapsed_seconds=%s",
            audio_record.id,
            generation_seconds,
        )
        return create_video_generation(
            audio_generation_id=audio_record.id,
            background_path=str(background_path),
            subtitle_path=str(subtitle_path),
            file_path=str(output_path),
            file_name=output_path.name,
            file_size_bytes=output_path.stat().st_size,
            duration_seconds=round(duration_seconds, 2),
            generation_seconds=generation_seconds,
            status="completed",
        )
    except Exception as error:
        if output_path is not None:
            output_path.unlink(missing_ok=True)
        generation_seconds = round(perf_counter() - started_at, 2)
        logger.exception(
            "video_generation_failed audio_generation_id=%s elapsed_seconds=%s",
            audio_record.id,
            generation_seconds,
        )
        create_video_generation(
            audio_generation_id=audio_record.id,
            background_path=str(background_path),
            subtitle_path=str(subtitle_path) if subtitle_path else None,
            generation_seconds=generation_seconds,
            status="failed",
            error_message=str(error),
        )
        if isinstance(error, VideoServiceError):
            raise
        if isinstance(error, TitleOverlayError):
            raise VideoServiceError(str(error)) from error
        raise VideoServiceError("Nu am putut genera videoclipul.") from error
    finally:
        if title_overlay_path is not None:
            title_overlay_path.unlink(missing_ok=True)
