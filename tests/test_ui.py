from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

from src.db import database
from src.ui.common import as_utc


@pytest.fixture(autouse=True)
def ready_database(isolated_store, monkeypatch):
    monkeypatch.setattr(database, "_database_ready", True)


def app():
    return AppTest.from_string("from src.app import run_app\nrun_app()", default_timeout=60)


def test_app_start_and_inactive_history_not_loaded(isolated_store):
    with (
        patch("src.ui.history_common.list_audio_generations") as audio,
        patch("src.ui.history_common.list_video_generations") as video,
    ):
        application = app().run()
        assert not application.exception
        application.text_area(key="text_input").set_value(
            "Hello world, this is an English message."
        ).run()
        assert not application.exception
        audio.assert_not_called()
        video.assert_not_called()


def test_same_rerun_text_and_generate(isolated_store):
    with patch("src.ui.generator_view.submit_job", return_value="test") as submit:
        application = app().run()
        application.text_area(key="text_input").set_value("Это сообщение для моих друзей.").run()
        application.text_area(key="text_input").set_value(
            "Hello world. This is a short English message."
        )
        next(
            button for button in application.button if button.label == "Generează MP3"
        ).click().run()
        assert not application.exception
        audio = submit.call_args.args[0]["audio"]
        assert audio["language"] == "Engleza" and audio["voice_name"] == "Jenny"
        assert audio["rate_percent"] == 2 and audio["title"].startswith("Hello")


def test_same_rerun_manual_language_and_generate(isolated_store):
    with patch("src.ui.generator_view.submit_job", return_value="test") as submit:
        application = app().run()
        application.text_area(key="text_input").set_value("Это сообщение для моих друзей.").run()
        application.checkbox(key="auto_settings_enabled").uncheck().run()
        application.selectbox(key="language_name").select("Engleza")
        next(
            button for button in application.button if button.label == "Generează MP3"
        ).click().run()
        assert not application.exception
        assert submit.call_args.args[0]["audio"]["voice_id"] == "en-US-JennyNeural"


def test_mp4_missing_tools_disabled(isolated_store):
    with patch(
        "src.ui.generator_view.validate_video_tools", side_effect=RuntimeError("FFmpeg lipsește")
    ):
        application = app().run()
        application.radio(key="output_format").set_value("MP4").run()
        assert not application.exception
        assert next(
            button for button in application.button if button.label == "Generează MP4"
        ).disabled


def test_history_utc():
    from datetime import UTC, datetime

    assert as_utc(datetime(2026, 10, 25, 1)).tzinfo == UTC


def test_form_survives_navigation(isolated_store):
    application = app().run()
    text = "This text must survive navigating to history."
    application.text_area(key="text_input").set_value(text).run()
    application.radio(key="navigation").set_value("Istoric audio").run()
    application.radio(key="navigation").set_value("Generator").run()
    assert not application.exception
    assert application.text_area(key="text_input").value == text


def test_video_defaults_and_settings_survive_format_switch(isolated_store):
    with patch("src.ui.generator_view.validate_video_tools"):
        application = app().run()
        application.radio(key="output_format").set_value("MP4").run()
        assert application.slider(key="intro_seconds").value == 3.0
        assert application.selectbox(key="crop_position").value == "center"
        application.slider(key="intro_seconds").set_value(4.5).run()
        application.selectbox(key="crop_position").select("right").run()
        application.radio(key="output_format").set_value("MP3").run()
        application.radio(key="output_format").set_value("MP4").run()
        assert application.slider(key="intro_seconds").value == 4.5
        assert application.selectbox(key="crop_position").value == "right"


def test_large_media_not_loaded_into_memory(isolated_store, audio_parameters):
    from src.config import MAX_DOWNLOAD_BYTES
    from src.db.repositories import create_audio_generation

    path = isolated_store / "audio" / "large.mp3"
    path.parent.mkdir()
    with path.open("wb") as output:
        output.truncate(MAX_DOWNLOAD_BYTES + 1)
    record = create_audio_generation(
        **audio_parameters, file_path="audio/large.mp3", status="completed"
    )
    with patch("src.ui.common._file_bytes") as read:
        application = AppTest.from_string(
            "from src.ui.common import render_media\n"
            "from src.db.repositories import get_record\n"
            "from src.db.models import AudioGeneration\n"
            f"render_media(get_record(AudioGeneration, {record.id}), 'audio', 'large')"
        ).run()
        assert not application.exception
        assert application.info and "Fișier mare" in application.info[0].value
        read.assert_not_called()
