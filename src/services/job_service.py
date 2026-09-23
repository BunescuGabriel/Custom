import json
import logging
from datetime import UTC, datetime
from threading import Thread
from uuid import uuid4

from filelock import FileLock, Timeout

from src.config import DATA_DIR
from src.db.database import get_session
from src.db.models import AudioGeneration, GenerationJob, VideoGeneration
from src.db.repositories import create_job, get_record, update_record
from src.services.audio_validation import audio_duration
from src.services.form_service import validate_request
from src.services.generation_service import generate_audio_record
from src.services.operations import GenerationCancelled, OperationControl, describe_error
from src.services.storage import resolve_media_path
from src.services.video_service import (
    _validate_background,
    generate_video_record,
    validate_video_tools,
)

logger = logging.getLogger(__name__)
ACTIVE_STATUSES = {"queued", "running"}


def generation_lock() -> FileLock:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return FileLock(str(DATA_DIR / "generation.lock"), timeout=0, thread_local=False)


def _recover_interrupted() -> None:
    with get_session() as session:
        session.query(GenerationJob).filter(GenerationJob.status.in_(ACTIVE_STATUSES)).update(
            {
                "status": "interrupted",
                "stage": "Procesarea a fost întreruptă",
                "error_message": "Aplicația s-a oprit înainte de finalizare. Poți relua din istoric.",
                "updated_at": datetime.now(UTC),
            },
            synchronize_session=False,
        )
        for model in (AudioGeneration, VideoGeneration):
            session.query(model).filter(model.status == "pending").update(
                {
                    "status": "interrupted",
                    "error_message": "Procesarea a fost întreruptă. Poți relua generarea.",
                },
                synchronize_session=False,
            )


def recover_interrupted_jobs() -> None:
    try:
        with generation_lock():
            _recover_interrupted()
    except Timeout:
        return


def cancel_job(job_id: str) -> None:
    with get_session() as session:
        session.query(GenerationJob).filter(
            GenerationJob.id == job_id, GenerationJob.status.in_(ACTIVE_STATUSES)
        ).update({"cancel_requested": True})


def _execute_job(job_id: str, parameters: dict, lock: FileLock) -> None:
    def update(**values):
        return update_record(GenerationJob, job_id, updated_at=datetime.now(UTC), **values)

    def cancelled():
        job = get_record(GenerationJob, job_id)
        return job is None or job.cancel_requested

    control = OperationControl(
        progress=lambda stage: update(stage=stage),
        cancelled=cancelled,
        record=lambda kind, record_id: update(**{f"{kind}_generation_id": record_id}),
    )
    try:
        update(status="running", stage="Verificare date")
        control.check()
        if parameters.get("background_path"):
            validate_video_tools()
            _validate_background(resolve_media_path(parameters["background_path"]), control)
        if parameters.get("audio_generation_id"):
            audio = get_record(AudioGeneration, parameters["audio_generation_id"])
            if audio is None or audio.status != "completed":
                raise ValueError("Audio-ul ales nu mai este disponibil.")
            audio_duration(resolve_media_path(audio.file_path))
            update(audio_generation_id=audio.id)
        else:
            audio = generate_audio_record(
                **parameters["audio"],
                control=control,
                force_synthesis=parameters.get("force_synthesis", False),
            )
            update(audio_generation_id=audio.id)
        if parameters.get("background_path"):
            video = generate_video_record(
                audio_record=audio,
                background_path=resolve_media_path(parameters["background_path"]),
                intro_seconds=parameters.get("intro_seconds", 3.0),
                crop_position=parameters.get("crop_position", "center"),
                allow_approximate=parameters.get("allow_approximate", False),
                control=control,
            )
            update(video_generation_id=video.id)
        update(status="completed", stage="Finalizat")
    except Exception as error:
        message = describe_error(error)
        try:
            update(
                status="cancelled" if isinstance(error, GenerationCancelled) else "failed",
                stage="Oprit",
                error_message=message,
            )
        except Exception:
            logger.exception("job_failure_record_unsaved job_id=%s", job_id)
    finally:
        lock.release()


def submit_job(parameters: dict) -> str:
    snapshot = json.loads(json.dumps(parameters))
    validate_request(snapshot["audio"])
    lock = generation_lock()
    try:
        lock.acquire()
    except Timeout as error:
        raise ValueError(
            "O altă generare este activă. Așteaptă finalizarea sau anuleaz-o din lista de lucrări."
        ) from error
    try:
        _recover_interrupted()
        job_id = uuid4().hex
        create_job(
            id=job_id,
            parameters=json.dumps(snapshot, ensure_ascii=False),
            status="queued",
            stage="În așteptare",
            cancel_requested=False,
        )
        worker = Thread(
            target=_execute_job,
            args=(job_id, snapshot, lock),
            daemon=True,
            name=f"generation-{job_id[:8]}",
        )
        worker.start()
        return job_id
    except BaseException:
        lock.release()
        raise
