import pytest

from src.services.form_service import normalize_form, validate_request
from src.services.text_analyzer import _detect_profile, recommend_audio_settings
from src.services.text_preprocessor import clean_text


def test_text_and_generate_use_same_snapshot():
    state = {
        "text_input": "Hello world. This is a short English message.",
        "title_input": "Old",
        "last_auto_title": "Old",
        "auto_settings_enabled": True,
        "language_name": "Rusa",
        "voice_name": "Dmitry",
        "rate_percent": -5,
    }
    request = normalize_form(state)
    assert (request["language"], request["voice_name"], request["rate_percent"]) == (
        "Engleza",
        "Jenny",
        2,
    )
    assert request["title"] == state["text_input"]
    assert request == normalize_form(state)


def test_language_and_generate_normalize_voice():
    state = {
        "text_input": "Hello world",
        "auto_settings_enabled": False,
        "language_name": "Engleza",
        "voice_name": "Dmitry",
    }
    request = normalize_form(state)
    assert request["voice_name"] == "Jenny"
    validate_request(request)


@pytest.mark.parametrize(
    "text,language",
    [
        ("Acesta este un mesaj pentru prietenii mei si pentru familia mea.", "Romana"),
        ("Je voudrais connaître les nouvelles de votre famille.", "Franceza"),
        ("connaître", "Franceza"),
        ("Dies ist eine Nachricht für meine Freunde und meine Familie.", "Germana"),
        ("Questa è una storia per tutti i miei amici.", "Italiana"),
        ("Esta es una historia para todos mis amigos.", "Spaniola"),
        ("Это короткое сообщение для моих друзей и моей семьи.", "Rusa"),
        ("This is a short message for my friends and family.", "Engleza"),
    ],
)
def test_supported_language(text, language):
    assert recommend_audio_settings(text).language_name == language


@pytest.mark.parametrize(
    "text",
    [
        "123",
        "Hi",
        "Це українська мова, повідомлення для моїх друзів.",
        "こんにちは、これは日本語です。",
    ],
)
def test_uncertain_or_unsupported_language(text):
    recommendation = recommend_audio_settings(text)
    assert recommendation.language_name is None
    assert recommendation.warning


def test_manual_override_survives_automatic_mode():
    state = {
        "text_input": "Hello world. This is an English message.",
        "auto_settings_enabled": True,
    }
    normalize_form(state)
    state["voice_name"] = "Guy"
    assert normalize_form(state)["voice_name"] == "Guy"


def test_real_paragraphs_only():
    assert clean_text("one\ntwo\n\nthree") == "one two\n\nthree"
    assert _detect_profile("one " * 50 + "\n" + "two " * 50) == "informative"


def test_resource_limit(audio_parameters):
    audio_parameters["text"] = "word " * 10000
    with pytest.raises(ValueError):
        validate_request(audio_parameters)
