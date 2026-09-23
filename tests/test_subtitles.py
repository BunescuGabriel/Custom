import json
from types import SimpleNamespace

import pytest

from src.services.subtitles import load_word_cues, write_subtitles


@pytest.mark.parametrize(
    "entry",
    [
        [],
        {},
        {"type": "WordBoundary", "text": "hello", "offset": -1, "duration": 100},
        {"type": "WordBoundary", "text": "hello", "offset": 0, "duration": -1},
        {"type": "WordBoundary", "text": "hello", "offset": 0, "duration": 100_000_000},
    ],
)
def test_invalid_metadata(tmp_path, entry):
    path = tmp_path / "words.jsonl"
    path.write_text(json.dumps(entry))
    assert load_word_cues(path, "hello", 1.0) == []


def test_incomplete_metadata_rejected(tmp_path):
    path = tmp_path / "words.jsonl"
    path.write_text(
        json.dumps({"type": "WordBoundary", "text": "hello", "offset": 0, "duration": 1_000_000})
    )
    assert load_word_cues(path, "hello world", 2.0) == []


def test_fallback_requires_opt_in_and_offsets_all_cues(valid_mp3):
    audio = SimpleNamespace(text="hello world")
    with pytest.raises(ValueError, match="aproximative"):
        write_subtitles(audio, valid_mp3, 2, 3, False)
    path, quality = write_subtitles(audio, valid_mp3, 2, 3, True)
    assert quality == "approximate"
    assert "Dialogue: 0,0:00:03.00,0:00:05.00" in path.read_text(encoding="utf-8-sig")
