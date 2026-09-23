import os
import tempfile

os.environ["APP_MEDIA_DIR"] = tempfile.mkdtemp(prefix="text-media-tests-")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src import config
from src.db import database, models
from src.services import (
    generation_service,
    job_service,
    media_service,
    storage,
    subtitles,
    title_overlay_service,
    tts_service,
    video_service,
)


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    media = tmp_path / "media"
    data = media / "data"
    data.mkdir(parents=True)
    paths = {
        "MEDIA_DIR": media,
        "DATA_DIR": data,
        "DATABASE_PATH": data / "app.db",
        "AUDIO_DIR": media / "audio",
        "BACKGROUND_DIR": media / "backgrounds",
        "VIDEO_DIR": media / "videos",
        "SUBTITLE_DIR": media / "videos" / "subtitles",
        "TITLE_OVERLAY_DIR": media / "videos" / "title_overlays",
    }
    modules = (
        config,
        database,
        generation_service,
        job_service,
        media_service,
        storage,
        subtitles,
        title_overlay_service,
        tts_service,
        video_service,
    )
    for module in modules:
        for name, path in paths.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, path)
    url = f"sqlite:///{(data / 'app.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})
    event.listen(engine, "connect", database._configure_sqlite)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=engine, autoflush=False))
    monkeypatch.setattr(database, "DATABASE_URL", url)
    monkeypatch.setattr(database, "_database_ready", False)
    models.Base.metadata.create_all(engine)
    yield media
    engine.dispose()


@pytest.fixture
def audio_parameters():
    return {
        "text": "Hello world. This is an English message.",
        "title": "Test audio",
        "language": "Engleza",
        "voice_name": "Jenny",
        "voice_id": "en-US-JennyNeural",
        "rate_percent": 2,
        "pitch_hz": 0,
    }


@pytest.fixture
def valid_mp3(isolated_store):
    path = isolated_store / "audio" / "valid.mp3"
    path.parent.mkdir()
    path.write_bytes((bytes.fromhex("fffb90c0") + bytes(413)) * 40)
    return path
