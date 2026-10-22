import json
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.config import MAX_UPLOAD_BYTES, VOICE_OPTIONS
from src.db.database import init_db
from src.db.models import AudioGeneration, GenerationJob, VideoGeneration
from src.db.repositories import (
    get_record,
    list_audio_generations,
    list_video_generations,
)
from src.logging_config import configure_logging
from src.services.job_service import cancel_job, recover_interrupted_jobs, submit_job
from src.services.media_service import save_background
from src.services.settings_service import current_settings, save_settings
from src.services.storage import media_reference, resolve_media_path


class AudioParameters(BaseModel):
    text: str = Field(max_length=12000)
    title: str = Field(max_length=140)
    language: str
    voice_name: str
    voice_id: str
    rate_percent: int = Field(default=0, ge=-40, le=40)
    pitch_hz: int = Field(default=0, ge=-20, le=20)


class GenerationRequest(BaseModel):
    audio: AudioParameters
    output_format: Literal["MP3", "MP4"] = "MP3"
    background_path: str | None = None
    intro_seconds: float | None = Field(default=None, ge=0, le=10)
    crop_position: Literal["left", "center", "right"] = "center"
    allow_approximate: bool = False
    force_synthesis: bool = False


class VocabularyRequest(BaseModel):
    text: str = Field(max_length=12000)
    title: str = Field(max_length=140)
    english_voice: str
    romanian_voice: str
    rate_percent: int = Field(default=0, ge=-40, le=40)
    english_pause_ms: int = Field(default=500, ge=0, le=3000)
    pair_pause_ms: int = Field(default=1000, ge=0, le=5000)


class SettingsRequest(BaseModel):
    video_width: int = Field(ge=480, le=3840, multiple_of=2)
    video_height: int = Field(ge=480, le=3840, multiple_of=2)
    video_fps: Literal[24, 30, 60]
    title_duration_seconds: float = Field(ge=0, le=10)
    default_rate_percent: int = Field(ge=-40, le=40)
    default_pitch_hz: int = Field(ge=-20, le=20)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _job_payload(job: GenerationJob) -> dict:
    parameters = json.loads(job.parameters)
    result = parameters.get("result", {})
    result_path = result.get("file_path")
    result_name = result.get("file_name")
    result_kind = "audio" if result_path else None
    audio_path = None
    audio_name = None
    if job.audio_generation_id:
        audio = get_record(AudioGeneration, job.audio_generation_id)
        if audio:
            audio_path = audio.file_path
            audio_name = audio.file_name
    if job.video_generation_id:
        video = get_record(VideoGeneration, job.video_generation_id)
        if video:
            result_path = video.file_path
            result_name = video.file_name
            result_kind = "video"
    elif audio_path:
        result_path = audio_path
        result_name = audio_name
        result_kind = "audio"
    return {
        "id": job.id,
        "status": job.status,
        "stage": job.stage,
        "cancel_requested": job.cancel_requested,
        "audio_generation_id": job.audio_generation_id,
        "video_generation_id": job.video_generation_id,
        "error_message": job.error_message,
        "created_at": _iso(job.created_at),
        "updated_at": _iso(job.updated_at),
        "result_url": _media_url(result_path),
        "result_name": result_name,
        "result_kind": result_kind,
        "audio_url": _media_url(audio_path),
        "audio_name": audio_name,
    }


def _media_url(path: str | None) -> str | None:
    return f"/api/media/{path}" if path else None


def _audio_payload(row) -> dict:
    return {
        "id": row.id,
        "title": row.title,
        "language": row.language,
        "voice_name": row.voice_name,
        "status": row.status,
        "duration_seconds": row.duration_seconds,
        "created_at": _iso(row.created_at),
        "file_url": _media_url(row.file_path),
        "file_name": row.file_name,
    }


def create_app() -> FastAPI:
    application = FastAPI(title="Custom API", version="0.1.0")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.on_event("startup")
    def startup() -> None:
        configure_logging()
        init_db()
        recover_interrupted_jobs()

    @application.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @application.get("/api/config")
    def configuration() -> dict:
        return {
            "voices": VOICE_OPTIONS,
            "limits": {"text_characters": 12000, "upload_bytes": MAX_UPLOAD_BYTES},
            "settings": current_settings(),
        }

    @application.put("/api/settings")
    def update_settings(request: SettingsRequest) -> dict:
        values = request.model_dump()
        if values["video_width"] * values["video_height"] > 3840 * 2160:
            raise HTTPException(400, "The selected video resolution is too large.")
        return save_settings(values)

    @application.post("/api/backgrounds", status_code=201)
    def upload_background(file: Annotated[UploadFile, File(...)]) -> dict:
        if not file.filename or Path(file.filename).suffix.lower() not in {
            ".mp4",
            ".mov",
            ".m4v",
            ".webm",
        }:
            raise HTTPException(400, "Upload an MP4, MOV, M4V, or WebM video background.")
        try:
            data = file.file.read(MAX_UPLOAD_BYTES + 1)
            if len(data) > MAX_UPLOAD_BYTES:
                raise HTTPException(413, "The background exceeds the 100 MB limit.")
            destination = save_background(file.filename, data)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        except OSError as error:
            raise HTTPException(500, "The background could not be saved.") from error
        finally:
            file.file.close()
        return {"path": media_reference(destination), "name": file.filename, "size": len(data)}

    @application.post("/api/jobs", status_code=202)
    def create_job(request: GenerationRequest) -> dict:
        parameters = request.model_dump()
        render_settings = current_settings()
        parameters["render_settings"] = render_settings
        if parameters["intro_seconds"] is None:
            parameters["intro_seconds"] = render_settings["title_duration_seconds"]
        if parameters["output_format"] == "MP4" and not parameters["background_path"]:
            raise HTTPException(400, "Choose a video background for MP4 output.")
        if parameters["output_format"] == "MP3":
            parameters["background_path"] = None
        try:
            job_id = submit_job(parameters)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        job = get_record(GenerationJob, job_id)
        return _job_payload(job)

    @application.post("/api/vocabulary/jobs", status_code=202)
    def create_vocabulary_job(request: VocabularyRequest) -> dict:
        try:
            job_id = submit_job(
                {"kind": "bilingual_vocabulary", "vocabulary": request.model_dump()}
            )
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        job = get_record(GenerationJob, job_id)
        return _job_payload(job)

    @application.get("/api/jobs/{job_id}")
    def job(job_id: str) -> dict:
        record = get_record(GenerationJob, job_id)
        if record is None:
            raise HTTPException(404, "The job does not exist.")
        return _job_payload(record)

    @application.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: str) -> dict:
        if get_record(GenerationJob, job_id) is None:
            raise HTTPException(404, "The job does not exist.")
        cancel_job(job_id)
        return {"status": "cancelling"}

    @application.get("/api/history/audio")
    def audio_history(limit: int = Query(default=50, ge=1, le=100)) -> list[dict]:
        return [_audio_payload(row) for row in list_audio_generations(limit=limit)]

    @application.get("/api/history/video")
    def video_history(limit: int = Query(default=50, ge=1, le=100)) -> list[dict]:
        return [
            {
                "id": row.id,
                "title": row.audio_generation.title,
                "status": row.status,
                "duration_seconds": row.duration_seconds,
                "created_at": _iso(row.created_at),
                "file_url": _media_url(row.file_path),
                "file_name": row.file_name,
            }
            for row in list_video_generations(limit=limit)
        ]

    @application.get("/api/media/{media_path:path}")
    def media(media_path: str):
        try:
            path = resolve_media_path(media_path)
        except ValueError as error:
            raise HTTPException(404, "The file is unavailable.") from error
        if not path.is_file():
            raise HTTPException(404, "The file is unavailable.")
        return FileResponse(path, filename=path.name, content_disposition_type="inline")

    return application


app = create_app()
