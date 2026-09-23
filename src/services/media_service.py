import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from filelock import Timeout

from src.config import AUDIO_DIR, BACKGROUND_DIR, MAX_UPLOAD_BYTES, MEDIA_DIR, VIDEO_DIR
from src.db.database import get_session
from src.db.models import AudioGeneration, GenerationJob, VideoGeneration
from src.services.job_service import generation_lock
from src.services.storage import resolve_media_path, safe_unlink, unique_path
from src.services.video_service import _validate_background, validate_video_tools


def save_background(name: str, data: bytes) -> Path:
    extension = Path(name).suffix.lower()
    if extension not in {".mp4", ".m4v", ".mov", ".webm"}:
        raise ValueError("Fundalul trebuie să fie MP4, M4V, MOV sau WebM.")
    if not 0 < len(data) <= MAX_UPLOAD_BYTES:
        raise ValueError("Fundalul trebuie să aibă între 1 octet și 100 MB.")
    validate_video_tools()
    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
    destination = BACKGROUND_DIR / f"{hashlib.sha256(data).hexdigest()}{extension}"
    if destination.is_file():
        _validate_background(destination)
        return destination
    temporary = unique_path(BACKGROUND_DIR, "upload", extension)
    try:
        temporary.write_bytes(data)
        _validate_background(temporary)
        temporary.replace(destination)
        return destination
    finally:
        safe_unlink(temporary)


def referenced_paths(session) -> set[Path]:
    paths = set()
    for model, columns in (
        (AudioGeneration, ("file_path",)),
        (VideoGeneration, ("file_path", "background_path", "subtitle_path")),
    ):
        for row in session.query(model).all():
            for column in columns:
                try:
                    path = resolve_media_path(getattr(row, column))
                except ValueError:
                    continue
                paths.add(path)
                if path.suffix == ".mp3":
                    paths.add(path.with_suffix(".jsonl"))
    for job in session.query(GenerationJob).all():
        try:
            parameters = json.loads(job.parameters)
            paths.add(resolve_media_path(parameters.get("background_path")))
        except (ValueError, TypeError):
            continue
    return paths


def delete_generation(kind: str, record_id: int) -> None:
    model = AudioGeneration if kind == "audio" else VideoGeneration
    try:
        with generation_lock():
            with get_session() as session:
                row = session.get(model, record_id)
                if row is None:
                    return
                if (
                    kind == "audio"
                    and session.query(VideoGeneration)
                    .filter_by(audio_generation_id=record_id)
                    .first()
                ):
                    raise ValueError("Șterge mai întâi videoclipurile asociate acestui audio.")
                candidates = []
                for column in ("file_path", "subtitle_path", "background_path"):
                    try:
                        path = resolve_media_path(getattr(row, column, None))
                    except ValueError:
                        continue
                    candidates.append(path)
                    if path.suffix == ".mp3":
                        candidates.append(path.with_suffix(".jsonl"))
                job_column = (
                    GenerationJob.audio_generation_id
                    if kind == "audio"
                    else GenerationJob.video_generation_id
                )
                session.query(GenerationJob).filter(job_column == record_id).delete(
                    synchronize_session=False
                )
                session.delete(row)
            with get_session() as session:
                referenced = referenced_paths(session)
            safe_unlink(*(path for path in candidates if path not in referenced))
    except Timeout as error:
        raise ValueError("Ștergerea este disponibilă după oprirea generării active.") from error


def cleanup_orphans(minimum_age_hours: int = 24) -> tuple[int, int]:
    removed = freed = 0
    try:
        with generation_lock():
            with get_session() as session:
                referenced = referenced_paths(session)
            cutoff = (datetime.now(UTC) - timedelta(hours=max(1, minimum_age_hours))).timestamp()
            for directory in (AUDIO_DIR, BACKGROUND_DIR, VIDEO_DIR):
                for path in directory.rglob("*") if directory.exists() else ():
                    if (
                        path.is_symlink()
                        or not path.is_file()
                        or not path.resolve().is_relative_to(MEDIA_DIR)
                    ):
                        continue
                    if path.resolve() in referenced or path.stat().st_mtime >= cutoff:
                        continue
                    size = path.stat().st_size
                    path.unlink()
                    removed += 1
                    freed += size
    except Timeout as error:
        raise ValueError("Curățarea este disponibilă după oprirea generării active.") from error
    return removed, freed


def delete_job(job_id: str) -> None:
    try:
        with generation_lock():
            with get_session() as session:
                row = session.get(GenerationJob, job_id)
                if row is not None:
                    session.delete(row)
    except Timeout as error:
        raise ValueError(
            "Ștergerea lucrărilor este disponibilă după oprirea generării active."
        ) from error


def storage_bytes() -> int:
    return sum(
        path.stat().st_size
        for directory in (AUDIO_DIR, BACKGROUND_DIR, VIDEO_DIR)
        for path in directory.rglob("*")
        if path.is_file() and not path.is_symlink()
    )
