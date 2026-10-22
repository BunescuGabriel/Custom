import pytest

from src.services.bilingual_vocabulary_service import (
    BilingualVocabularyError,
    parse_vocabulary_pairs,
    validate_bilingual_request,
)


def test_parse_vocabulary_pairs_keeps_each_language_separate():
    pairs = parse_vocabulary_pairs("Improve | A îmbunătăți\nChoose | A alege")
    assert [(pair.english, pair.romanian) for pair in pairs] == [
        ("Improve", "A îmbunătăți"),
        ("Choose", "A alege"),
    ]


@pytest.mark.parametrize(
    "text", ["Improve A îmbunătăți", "Improve | A îmbunătăți | Extra", " | A alege"]
)
def test_parse_vocabulary_pairs_reports_invalid_lines(text):
    with pytest.raises(BilingualVocabularyError):
        parse_vocabulary_pairs(text)


def test_validate_bilingual_request_accepts_configured_voices():
    pairs = validate_bilingual_request(
        {
            "text": "Improve | A îmbunătăți",
            "title": "Verbe",
            "english_voice": "en-US-JennyNeural",
            "romanian_voice": "ro-RO-AlinaNeural",
            "rate_percent": 0,
            "english_pause_ms": 600,
            "pair_pause_ms": 1000,
        }
    )
    assert len(pairs) == 1
