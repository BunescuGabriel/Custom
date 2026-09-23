from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from src.config import BASE_DIR
from src.db import database
from src.db.models import AudioGeneration, Base
from src.db.repositories import (
    create_audio_generation,
    create_video_generation,
    get_record,
    list_audio_generations,
)
from src.services.media_service import delete_generation
from src.services.storage import media_reference, resolve_media_path


def test_foreign_keys_enforced(isolated_store):
    with database.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    with pytest.raises(IntegrityError):
        create_video_generation(audio_generation_id=987, background_path="backgrounds/test.mp4")


def test_migrations_match_metadata(isolated_store):
    Base.metadata.drop_all(database.engine)
    database.init_db()
    with database.engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_existing_history_migrates_portable_paths(isolated_store):
    Base.metadata.drop_all(database.engine)
    configuration = Config(str(BASE_DIR / "alembic.ini"))
    configuration.attributes.update(database_url=database.DATABASE_URL, configure_logger=False)
    command.upgrade(configuration, "20260922_0004")
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO audio_generations (id,title,text,content_hash,language,voice_name,voice_id,rate_percent,pitch_hz,status,created_at,file_path) VALUES (1,'Old','Text','hash','Engleza','Jenny','voice',0,0,'completed','2026-09-01 00:00:00','C:/old/project/media/audio/old.mp3')"
            )
        )
    command.upgrade(configuration, "head")
    row = get_record(AudioGeneration, 1)
    assert row.title == "Old" and row.file_path == "audio/old.mp3"
    assert resolve_media_path(row.file_path) == isolated_store / "audio" / "old.mp3"


def test_parallel_database_initialization(isolated_store):
    Base.metadata.drop_all(database.engine)
    with ThreadPoolExecutor(4) as executor:
        list(executor.map(lambda _: database.init_db(), range(4)))
    with database.engine.connect() as connection:
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []


def test_shared_audio_deleted_only_after_last_reference(valid_mp3, audio_parameters):
    first = create_audio_generation(**audio_parameters, file_path=media_reference(valid_mp3))
    second = create_audio_generation(**audio_parameters, file_path=media_reference(valid_mp3))
    delete_generation("audio", first.id)
    assert valid_mp3.exists()
    delete_generation("audio", second.id)
    assert not valid_mp3.exists()


def test_delete_linked_audio_is_blocked(valid_mp3, audio_parameters):
    audio = create_audio_generation(**audio_parameters, file_path=media_reference(valid_mp3))
    create_video_generation(audio_generation_id=audio.id, background_path="backgrounds/a.mp4")
    with pytest.raises(ValueError, match="mai întâi"):
        delete_generation("audio", audio.id)
    assert valid_mp3.exists()


def test_pagination_search_and_status(isolated_store, audio_parameters):
    for index in range(55):
        create_audio_generation(
            **{**audio_parameters, "title": f"Record {index}"},
            status="failed" if index % 2 else "completed",
        )
    assert len(list_audio_generations(limit=25, offset=50)) == 5
    assert all(row.status == "failed" for row in list_audio_generations(status="failed"))
    assert len(list_audio_generations(search="Record 54")) == 1


def test_path_traversal_and_empty_path_rejected(isolated_store):
    for path in ("", "../other.mp3", "C:/outside/private.txt"):
        with pytest.raises(ValueError):
            resolve_media_path(path)
