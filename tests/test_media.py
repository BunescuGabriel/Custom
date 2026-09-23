import os
import time

import pytest

from src.db.repositories import create_audio_generation
from src.services import media_service
from src.services.storage import media_reference


def test_background_validation_never_publishes_bad_upload(isolated_store, monkeypatch):
    monkeypatch.setattr(media_service, "validate_video_tools", lambda: None)
    monkeypatch.setattr(
        media_service,
        "_validate_background",
        lambda _: (_ for _ in ()).throw(ValueError("Invalid video")),
    )
    with pytest.raises(ValueError):
        media_service.save_background("bad.mp4", b"invalid")
    assert not list(isolated_store.rglob("*.mp4"))


def test_background_content_is_reused(isolated_store, monkeypatch):
    monkeypatch.setattr(media_service, "validate_video_tools", lambda: None)
    monkeypatch.setattr(media_service, "_validate_background", lambda _: {})
    first = media_service.save_background("first.mp4", b"same content")
    second = media_service.save_background("second.mp4", b"same content")
    assert first == second
    assert len(list(first.parent.iterdir())) == 1


def test_cleanup_preserves_active_references_and_recent_files(valid_mp3, audio_parameters):
    create_audio_generation(**audio_parameters, file_path=media_reference(valid_mp3))
    orphan = valid_mp3.parent / "orphan.part.mp3"
    recent = valid_mp3.parent / "recent.mp3"
    orphan.write_bytes(b"old partial")
    recent.write_bytes(b"recent")
    old = time.time() - 48 * 3600
    os.utime(valid_mp3, (old, old))
    os.utime(orphan, (old, old))
    removed, freed = media_service.cleanup_orphans()
    assert removed == 1 and freed == len(b"old partial")
    assert valid_mp3.exists() and recent.exists() and not orphan.exists()
