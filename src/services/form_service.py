from collections.abc import MutableMapping

from src.config import MAX_AUDIO_SECONDS, MAX_TEXT_CHARACTERS, VOICE_OPTIONS
from src.services.text_analyzer import recommend_audio_settings
from src.services.text_preprocessor import clean_text, make_title


def normalize_form(state: MutableMapping) -> dict:
    text = clean_text(state.get("text_input", ""))
    if text != state.get("last_title_source_text", ""):
        suggested = make_title(text)
        if not state.get("title_input", "").strip() or state["title_input"] == state.get(
            "last_auto_title"
        ):
            state["title_input"] = suggested
        state["last_auto_title"] = suggested
        state["last_title_source_text"] = text
    if state.get("auto_settings_enabled") and text != state.get("last_recommendation_text"):
        recommendation = recommend_audio_settings(text)
        state["language_warning"] = recommendation.warning
        state["detected_profile"] = recommendation.profile_name
        if recommendation.language_name:
            state["language_name"] = recommendation.language_name
            state["voice_name"] = recommendation.voice_name
            state["rate_percent"] = recommendation.rate_percent
            state["pitch_hz"] = recommendation.pitch_hz
        state["last_recommendation_text"] = text
    language = state.get("language_name", "Romana")
    if language not in VOICE_OPTIONS:
        language = "Romana"
        state["language_name"] = language
    if state.get("voice_name") not in VOICE_OPTIONS[language]:
        state["voice_name"] = next(iter(VOICE_OPTIONS[language]))
    return {
        "text": text,
        "title": state.get("title_input", "").strip() or make_title(text),
        "language": language,
        "voice_name": state["voice_name"],
        "voice_id": VOICE_OPTIONS[language][state["voice_name"]],
        "rate_percent": int(state.get("rate_percent", 0)),
        "pitch_hz": int(state.get("pitch_hz", 0)),
    }


def estimate_seconds(text: str, rate_percent: int = 0) -> float:
    return max(len(text.split()) / 2.2, len(text) / 14) / (1 + rate_percent / 100)


def validate_request(request: dict) -> None:
    if not request["text"].strip():
        raise ValueError("Textul nu poate fi gol.")
    if len(request["text"]) > MAX_TEXT_CHARACTERS:
        raise ValueError(f"Textul poate avea cel mult {MAX_TEXT_CHARACTERS} de caractere.")
    if len(request["title"]) > 140:
        raise ValueError("Titlul poate avea cel mult 140 de caractere.")
    if not -40 <= request["rate_percent"] <= 40 or not -20 <= request["pitch_hz"] <= 20:
        raise ValueError("Viteza sau tonul sunt în afara intervalului permis.")
    if VOICE_OPTIONS.get(request["language"], {}).get(request["voice_name"]) != request["voice_id"]:
        raise ValueError("Vocea nu corespunde limbii selectate.")
    if estimate_seconds(request["text"], request["rate_percent"]) > MAX_AUDIO_SECONDS:
        raise ValueError("Durata estimată depășește 10 minute. Împarte textul în fragmente.")
