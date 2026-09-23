import re
from dataclasses import dataclass
from functools import lru_cache

from lingua import Language, LanguageDetectorBuilder

from src.config import AUDIO_PROFILES
from src.services.text_preprocessor import clean_text

LANGUAGES = {
    Language.ROMANIAN: "Romana",
    Language.RUSSIAN: "Rusa",
    Language.ENGLISH: "Engleza",
    Language.FRENCH: "Franceza",
    Language.GERMAN: "Germana",
    Language.ITALIAN: "Italiana",
    Language.SPANISH: "Spaniola",
}


@dataclass(frozen=True)
class AudioRecommendation:
    language_name: str | None
    voice_name: str | None
    profile_name: str
    rate_percent: int
    pitch_hz: int
    warning: str | None = None


@lru_cache(maxsize=1)
def _detector():
    return (
        LanguageDetectorBuilder.from_all_languages()
        .with_low_accuracy_mode()
        .with_minimum_relative_distance(0.1)
        .build()
    )


@lru_cache(maxsize=64)
def _detect_language(text: str) -> tuple[str | None, str | None]:
    if sum(character.isalpha() for character in text) < 5:
        return None, "Text prea scurt pentru detectare sigură. Alege limba manual."
    detector = _detector()
    language = detector.detect_language_of(text)
    if language not in LANGUAGES:
        return None, "Limba este incertă sau nesuportată. Alege limba manual."
    sentences = [sentence for sentence in re.split(r"[.!?\n]+", text) if len(sentence.split()) >= 3]
    significant = {detector.detect_language_of(sentence) for sentence in sentences}
    significant.discard(None)
    letters = [character for character in text if character.isalpha()]
    cyrillic_ratio = sum("\u0400" <= character <= "\u04ff" for character in letters) / len(letters)
    if len(significant) > 1 or 0.2 < cyrillic_ratio < 0.8:
        return None, "Textul pare să combine mai multe limbi. Alege limba manual."
    return LANGUAGES[language], None


def _detect_profile(text: str) -> str:
    cleaned = clean_text(text)
    if len(cleaned) < 300:
        return "short_message"
    sentences = sum(cleaned.count(mark) for mark in ".!?")
    if sum(character.isdigit() for character in cleaned) >= 8 and sentences <= 8:
        return "informative"
    if cleaned.count("—") + cleaned.count("- ") >= 3:
        return "dialogue"
    paragraphs = [paragraph for paragraph in re.split(r"\n\s*\n", cleaned) if paragraph.strip()]
    if len(paragraphs) >= 3 or sentences >= 8 or len(cleaned) >= 900:
        return "story"
    return "informative"


def recommend_audio_settings(text: str) -> AudioRecommendation:
    language, warning = _detect_language(clean_text(text))
    profile_name = _detect_profile(text)
    profile = AUDIO_PROFILES[profile_name]
    return AudioRecommendation(
        language,
        profile["voice_by_language"].get(language),
        profile_name,
        profile["rate_percent"],
        profile["pitch_hz"],
        warning,
    )
