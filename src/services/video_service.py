import json
import logging
import math
import shutil
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from src.config import (
    MAX_BACKGROUND_SECONDS,
    MAX_UPLOAD_BYTES,
    MAX_VIDEO_PIXELS,
    VIDEO_DIR,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_RENDER_TIMEOUT_SECONDS,
    VIDEO_TITLE_DURATION_SECONDS,
    VIDEO_TITLE_PREVIEW_SECONDS,
    VIDEO_WIDTH,
)
from src.db.models import AudioGeneration, VideoGeneration
from src.db.repositories import create_video_generation, update_record
from src.services.audio_validation import audio_duration
from src.services.operations import (
    GenerationCancelled,
    OperationControl,
    describe_error,
    run_process,
)
from src.services.storage import media_reference, resolve_media_path, safe_unlink, unique_path
from src.services.subtitles import write_subtitles
from src.services.text_preprocessor import make_file_stem
from src.services.title_overlay_service import create_title_overlay, resolve_font

logger = logging.getLogger(__name__)


class VideoServiceError(RuntimeError):
    pass


def is_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _get_ffmpeg_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise VideoServiceError(
            "MP4 necesită FFmpeg și FFprobe în PATH. Instalează-le și repornește aplicația."
        )
    return executable


@lru_cache(maxsize=4)
def _check_capabilities(ffmpeg: str, modified: float) -> None:
    for option, required in (
        ("-filters", ("ass", "overlay", "concat", "scale", "crop")),
        ("-encoders", ("libx264", "aac")),
    ):
        result = run_process([ffmpeg, "-hide_banner", option], 15)
        names = {parts[1] for line in result.stdout.splitlines() if len(parts := line.split()) > 1}
        if result.returncode or not set(required) <= names:
            raise VideoServiceError(
                "FFmpeg trebuie să includă libass, libx264 și AAC. Instalează o versiune completă."
            )


def validate_video_tools() -> None:
    ffmpeg = _get_ffmpeg_executable("ffmpeg")
    _get_ffmpeg_executable("ffprobe")
    _check_capabilities(ffmpeg, Path(ffmpeg).stat().st_mtime)
    resolve_font()


def _validate_background(background_path: Path, control: OperationControl | None = None) -> dict:
    if not background_path.is_file() or not 0 < background_path.stat().st_size <= MAX_UPLOAD_BYTES:
        raise VideoServiceError("Fundalul lipsește, este gol sau depășește 100 MB.")
    result = run_process(
        [
            _get_ffmpeg_executable("ffprobe"),
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_type,width,height:format=duration",
            "-of",
            "json",
            str(background_path),
        ],
        30,
        control,
    )
    try:
        metadata = json.loads(result.stdout)
        stream = metadata["streams"][0]
        width, height = int(stream["width"]), int(stream["height"])
        duration = float(metadata["format"]["duration"])
        if (
            result.returncode
            or width <= 0
            or height <= 0
            or width * height > MAX_VIDEO_PIXELS
            or max(width, height) > 4096
        ):
            raise ValueError("Invalid resolution")
        if not math.isfinite(duration) or not 0 < duration <= MAX_BACKGROUND_SECONDS:
            raise ValueError("Invalid duration")
    except (KeyError, IndexError, TypeError, ValueError) as error:
        logger.warning("background_validation_failed details=%s", result.stderr)
        raise VideoServiceError(
            "Fundal incompatibil. Folosește un video de maximum 4K, 100 MB și 10 minute."
        ) from error
    return {"width": width, "height": height, "duration": duration}


def _crop_filter(position: str) -> str:
    if position not in {"left", "center", "right"}:
        raise ValueError("Poziția decupării nu este validă.")
    horizontal = {"left": "0", "center": "(iw-ow)/2", "right": "iw-ow"}[position]
    return f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}:{horizontal}:(ih-oh)/2,setsar=1"


def extract_preview(
    background_path: Path, crop_position: str = "center", control: OperationControl | None = None
) -> Path:
    info = _validate_background(background_path, control)
    path = unique_path(VIDEO_DIR / "previews", "frame", ".png")
    try:
        result = run_process(
            [
                _get_ffmpeg_executable("ffmpeg"),
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                str(min(VIDEO_TITLE_PREVIEW_SECONDS, info["duration"] / 2)),
                "-i",
                str(background_path),
                "-vf",
                _crop_filter(crop_position),
                "-frames:v",
                "1",
                "-threads",
                "2",
                str(path),
            ],
            30,
            control,
        )
        if result.returncode or not path.is_file():
            logger.error("frame_extraction_failed details=%s", result.stderr)
            raise VideoServiceError("Nu pot decoda fundalul. Încearcă un alt videoclip.")
        return path
    except BaseException:
        safe_unlink(path)
        raise


def _make_output_path(file_stem: str) -> Path:
    return unique_path(VIDEO_DIR, file_stem, ".mp4")


def _render_video(
    background_path: Path,
    audio_path: Path,
    subtitle_path: Path,
    title_overlay_path: Path,
    duration_seconds: float,
    intro_seconds: float = VIDEO_TITLE_DURATION_SECONDS,
    crop_position: str = "center",
    control: OperationControl | None = None,
) -> Path:
    ffmpeg = _get_ffmpeg_executable("ffmpeg")
    output = _make_output_path(audio_path.stem)
    temporary = output.with_name(output.stem + ".part.mp4")
    frame = None
    work_dir = unique_path(VIDEO_DIR, "render", "")
    work_dir.mkdir()
    try:
        shutil.copyfile(subtitle_path, work_dir / "subtitles.ass")
        font_path = Path(resolve_font())
        shutil.copyfile(font_path, work_dir / font_path.name)
        background = (
            f"[0:v]{_crop_filter(crop_position)},fps={VIDEO_FPS},setpts=PTS-STARTPTS[background];"
        )
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-filter_complex_threads",
            "2",
            "-stream_loop",
            "-1",
            "-i",
            str(background_path),
            "-i",
            str(audio_path),
        ]
        if intro_seconds > 0:
            frame = extract_preview(background_path, crop_position, control)
            command += [
                "-loop",
                "1",
                "-framerate",
                str(VIDEO_FPS),
                "-i",
                str(title_overlay_path),
                "-loop",
                "1",
                "-framerate",
                str(VIDEO_FPS),
                "-i",
                str(frame),
            ]
            opening = (
                f"[3:v][2:v]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2,"
                f"trim=duration={intro_seconds},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[opening];"
                "[opening][background]concat=n=2:v=1:a=0[sequence];"
            )
            source = "sequence"
        else:
            opening = ""
            source = "background"
        graph = (
            background + opening + f"[{source}]ass=filename=subtitles.ass:fontsdir=.[video];"
            f"[1:a]adelay={round(intro_seconds * 1000)}:all=1[narration]"
        )
        command += [
            "-filter_complex",
            graph,
            "-map",
            "[video]",
            "-map",
            "[narration]",
            "-t",
            f"{duration_seconds + intro_seconds:.3f}",
            "-c:v",
            "libx264",
            "-threads",
            "2",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(temporary),
        ]
        result = run_process(command, VIDEO_RENDER_TIMEOUT_SECONDS, control, cwd=work_dir)
        if result.returncode or not temporary.is_file() or temporary.stat().st_size == 0:
            logger.error("video_render_failed details=%s", result.stderr)
            raise VideoServiceError(
                "FFmpeg nu a putut crea videoclipul. Încearcă alt fundal; detaliile sunt în jurnal."
            )
        if control:
            control.check()
        temporary.replace(output)
        return output
    finally:
        safe_unlink(temporary, frame)
        try:
            for path in work_dir.iterdir():
                safe_unlink(path)
            work_dir.rmdir()
        except OSError:
            logger.warning("render_directory_cleanup_failed path=%s", work_dir)


def generate_video_record(
    *,
    audio_record: AudioGeneration,
    background_path: Path,
    intro_seconds: float = VIDEO_TITLE_DURATION_SECONDS,
    crop_position: str = "center",
    allow_approximate: bool = False,
    control: OperationControl | None = None,
) -> VideoGeneration:
    control = control or OperationControl()
    validate_video_tools()
    if not 0 <= intro_seconds <= 10:
        raise ValueError("Introducerea trebuie să aibă între 0 și 10 secunde.")
    _crop_filter(crop_position)
    audio_path = resolve_media_path(audio_record.file_path)
    if audio_record.status != "completed":
        raise VideoServiceError("Audio-ul necesar pentru videoclip nu este disponibil.")
    duration = audio_duration(audio_path)
    _validate_background(background_path, control)
    record = create_video_generation(
        audio_generation_id=audio_record.id,
        background_path=media_reference(background_path),
        intro_seconds=intro_seconds,
        crop_position=crop_position,
        status="pending",
    )
    started = perf_counter()
    subtitle_path = title_path = output_path = None
    try:
        control.record("video", record.id)
        control.report("Pregătire subtitrări")
        subtitle_path, quality = write_subtitles(
            audio_record, audio_path, duration, intro_seconds, allow_approximate
        )
        title_path = create_title_overlay(audio_record.title)
        control.report("Randare MP4")
        output_path = _render_video(
            background_path,
            audio_path,
            subtitle_path,
            title_path,
            duration,
            intro_seconds,
            crop_position,
            control,
        )
        return update_record(
            VideoGeneration,
            record.id,
            subtitle_path=media_reference(subtitle_path),
            file_path=media_reference(output_path),
            file_name=make_file_stem(audio_record.title) + ".mp4",
            file_size_bytes=output_path.stat().st_size,
            duration_seconds=round(duration + intro_seconds, 2),
            generation_seconds=round(perf_counter() - started, 2),
            subtitle_quality=quality,
            status="completed",
        )
    except Exception as error:
        safe_unlink(output_path, subtitle_path)
        message = describe_error(error)
        try:
            update_record(
                VideoGeneration,
                record.id,
                status="cancelled" if isinstance(error, GenerationCancelled) else "failed",
                error_message=message,
                generation_seconds=round(perf_counter() - started, 2),
            )
        except Exception:
            logger.exception("video_failure_record_unsaved id=%s", record.id)
        raise
    finally:
        safe_unlink(title_path)
