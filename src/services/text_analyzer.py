from dataclasses import dataclass

from src.config import AUDIO_PROFILES, VOICE_OPTIONS
from src.services.text_preprocessor import clean_text


@dataclass(frozen=True)
class AudioRecommendation:
    language_name: str
    voice_name: str
    profile_name: str
    rate_percent: int
    pitch_hz: int


def _count_cyrillic(text: str) -> int:
    return sum(1 for char in text if "\u0400" <= char <= "\u04ff")


def _detect_language(text: str) -> str:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return "Rusa"

    cyrillic_ratio = _count_cyrillic(text) / len(letters)
    if cyrillic_ratio >= 0.35:
        return "Rusa"

    romanian_codepoints = {
        0x0103,
        0x00E2,
        0x00EE,
        0x0219,
        0x021B,
        0x015F,
        0x0163,
        0x0102,
        0x00C2,
        0x00CE,
        0x0218,
        0x021A,
        0x015E,
        0x0162,
    }
    if any(ord(char) in romanian_codepoints for char in text):
        return "Romana"

    return "Engleza"


def _detect_profile(text: str) -> str:
    cleaned_text = clean_text(text)
    if not cleaned_text:
        return "short_message"

    paragraphs = cleaned_text.splitlines()
    paragraph_count = len(paragraphs)
    sentence_count = sum(cleaned_text.count(mark) for mark in ".!?")
    dialogue_count = cleaned_text.count("\u2014") + cleaned_text.count("- ")
    digit_count = sum(1 for char in cleaned_text if char.isdigit())
    text_length = len(cleaned_text)

    if text_length < 300:
        return "short_message"

    if digit_count >= 8 and sentence_count <= 8:
        return "informative"

    if dialogue_count >= 3:
        return "dialogue"

    if paragraph_count >= 3 or sentence_count >= 8 or text_length >= 900:
        return "story"

    return "informative"


def recommend_audio_settings(text: str) -> AudioRecommendation:
    language_name = _detect_language(text)
    profile_name = _detect_profile(text)
    profile = AUDIO_PROFILES[profile_name]

    voice_name = profile["voice_by_language"].get(language_name)
    if voice_name not in VOICE_OPTIONS[language_name]:
        voice_name = next(iter(VOICE_OPTIONS[language_name]))

    return AudioRecommendation(
        language_name=language_name,
        voice_name=voice_name,
        profile_name=profile_name,
        rate_percent=profile["rate_percent"],
        pitch_hz=profile["pitch_hz"],
    )
