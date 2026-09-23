import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

import pytest
from aiohttp import ClientResponseError

from src.db.models import AudioGeneration
from src.db.repositories import create_audio_generation, get_record, list_audio_generations
from src.services import generation_service, tts_service
from src.services.audio_validation import audio_duration
from src.services.operations import GenerationCancelled, OperationControl
from src.services.storage import media_reference


def test_audio_integrity(valid_mp3):
    assert audio_duration(valid_mp3) > 0
    valid_mp3.write_bytes(b"not an mp3")
    with pytest.raises(ValueError):
        audio_duration(valid_mp3)


def test_concurrent_tts_never_overwrites(isolated_store, monkeypatch):
    barrier = Barrier(2)

    async def save(text, voice, rate, pitch, path, control):
        barrier.wait(timeout=5)
        path.write_text(text)
        path.with_suffix(".jsonl").write_text("{}")

    monkeypatch.setattr(tts_service, "_save_audio", save)
    with ThreadPoolExecutor(2) as executor:
        first = executor.submit(tts_service.text_to_audio, "first", "voice", file_stem="same")
        second = executor.submit(tts_service.text_to_audio, "second", "voice", file_stem="same")
        paths = [first.result(), second.result()]
    assert paths[0] != paths[1]
    assert {path.read_text() for path in paths} == {"first", "second"}
    assert not list(isolated_store.rglob("*.part.*"))


def test_cache_skips_bad_latest_and_reuses_older(valid_mp3, audio_parameters, monkeypatch):
    older = create_audio_generation(
        **audio_parameters, status="completed", file_path=media_reference(valid_mp3)
    )
    newer = create_audio_generation(
        **audio_parameters, status="completed", file_path="audio/missing.mp3"
    )
    monkeypatch.setattr(
        generation_service, "text_to_audio", lambda *args: pytest.fail("cache should avoid TTS")
    )
    result = generation_service.generate_audio_record(**audio_parameters)
    assert result.cache_hit and result.file_path == older.file_path
    assert get_record(AudioGeneration, newer.id).status == "unavailable"
    assert len(list(valid_mp3.parent.glob("*.mp3"))) == 1


def test_corrupt_cache_regenerates(valid_mp3, audio_parameters, monkeypatch):
    bad = valid_mp3.parent / "bad.mp3"
    bad.write_bytes(b"garbage")
    create_audio_generation(**audio_parameters, status="completed", file_path=media_reference(bad))
    monkeypatch.setattr(generation_service, "text_to_audio", lambda *args: valid_mp3)
    result = generation_service.generate_audio_record(**audio_parameters)
    assert result.status == "completed" and not result.cache_hit


def test_database_failure_cleans_owned_files_preserves_original(
    valid_mp3, audio_parameters, monkeypatch
):
    monkeypatch.setattr(generation_service, "text_to_audio", lambda *args: valid_mp3)
    cause = RuntimeError("database unavailable")
    monkeypatch.setattr(
        generation_service, "update_record", lambda *args, **kwargs: (_ for _ in ()).throw(cause)
    )
    with pytest.raises(RuntimeError) as caught:
        generation_service.generate_audio_record(**audio_parameters)
    assert caught.value is cause
    assert not valid_mp3.exists()


def test_tts_failure_keeps_failed_record(isolated_store, audio_parameters, monkeypatch):
    monkeypatch.setattr(
        generation_service, "text_to_audio", lambda *args: (_ for _ in ()).throw(TimeoutError())
    )
    with pytest.raises(TimeoutError):
        generation_service.generate_audio_record(**audio_parameters)
    record = list_audio_generations()[0]
    assert record.status == "failed"
    assert "expirat" in record.error_message


@pytest.mark.parametrize(
    "status,should_retry", [(401, False), (400, False), (429, True), (500, True), (503, True)]
)
def test_retry_classification(status, should_retry):
    error = ClientResponseError(SimpleNamespace(real_url="https://example.test"), (), status=status)
    assert (tts_service._retry_delay(error, 1) is not None) == should_retry


def test_retry_after_and_network_timeout():
    error = ClientResponseError(
        SimpleNamespace(real_url="https://example.test"),
        (),
        status=429,
        headers={"Retry-After": "7"},
    )
    assert tts_service._retry_delay(error, 1) == 7
    assert tts_service._retry_delay(TimeoutError(), 1) >= 1
    error.headers = {"Retry-After": "120"}
    assert tts_service._retry_delay(error, 1) == 120


def test_permanent_http_error_only_attempted_once(isolated_store, monkeypatch):
    calls = []

    class Provider:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        async def save(self, *args):
            raise ClientResponseError(
                SimpleNamespace(real_url="https://example.test"), (), status=401
            )

    monkeypatch.setattr(tts_service.edge_tts, "Communicate", Provider)
    with pytest.raises(ClientResponseError):
        tts_service.text_to_audio("text", "voice")
    assert len(calls) == 1
    assert not list(isolated_store.rglob("*.mp3"))


def test_tts_deadline_removes_partial_files(isolated_store, monkeypatch):
    async def interrupted(text, voice, rate, pitch, path, control):
        path.write_bytes(b"partial")
        path.with_suffix(".jsonl").write_text("{}")
        await asyncio.sleep(10)

    monkeypatch.setattr(tts_service, "_save_audio", interrupted)
    monkeypatch.setattr(tts_service, "TTS_TIMEOUT_SECONDS", 0.01)
    with pytest.raises(TimeoutError):
        tts_service.text_to_audio("text", "voice")
    assert not list(isolated_store.rglob("*.mp3"))
    assert not list(isolated_store.rglob("*.jsonl"))


def test_cancelled_synthesis_never_calls_provider(isolated_store, monkeypatch):
    monkeypatch.setattr(
        tts_service.edge_tts, "Communicate", lambda **kwargs: pytest.fail("cancelled request")
    )
    with pytest.raises(GenerationCancelled):
        tts_service.text_to_audio("text", "voice", control=OperationControl(cancelled=lambda: True))
    assert not list(isolated_store.rglob("*.mp3"))
