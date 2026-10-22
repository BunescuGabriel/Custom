import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.config import AUDIO_DIR, MAX_AUDIO_SECONDS, MAX_TEXT_CHARACTERS, VOICE_OPTIONS
from src.services.audio_validation import audio_duration
from src.services.operations import OperationControl, run_process
from src.services.storage import safe_unlink, unique_path
from src.services.text_preprocessor import make_file_stem
from src.services.tts_service import text_to_audio


class BilingualVocabularyError(ValueError):
    pass


@dataclass(frozen=True)
class VocabularyPair:
    english: str
    romanian: str


def parse_vocabulary_pairs(text: str) -> list[VocabularyPair]:
    if len(text) > MAX_TEXT_CHARACTERS:
        raise BilingualVocabularyError(
            f"Lista poate avea cel mult {MAX_TEXT_CHARACTERS} de caractere."
        )
    pairs = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.count("|") != 1:
            raise BilingualVocabularyError(
                f"Line {line_number} must contain exactly one | separator."
            )
        english, romanian = (part.strip() for part in line.split("|"))
        if not english or not romanian:
            raise BilingualVocabularyError(
                f"Line {line_number} must have an English term and a Romanian translation."
            )
        pairs.append(VocabularyPair(english=english, romanian=romanian))
    if not pairs:
        raise BilingualVocabularyError("Add at least one vocabulary pair.")
    return pairs


def validate_bilingual_request(request: dict) -> list[VocabularyPair]:
    pairs = parse_vocabulary_pairs(request.get("text", ""))
    title = request.get("title", "").strip()
    if not title or len(title) > 140:
        raise BilingualVocabularyError("The title must contain 1 to 140 characters.")
    if request.get("english_voice") not in VOICE_OPTIONS["Engleza"].values():
        raise BilingualVocabularyError("The English voice is invalid.")
    if request.get("romanian_voice") not in VOICE_OPTIONS["Romana"].values():
        raise BilingualVocabularyError("The Romanian voice is invalid.")
    for key in ("rate_percent", "english_pause_ms", "pair_pause_ms"):
        if not isinstance(request.get(key), int):
            raise BilingualVocabularyError("The vocabulary settings are invalid.")
    if not -40 <= request["rate_percent"] <= 40:
        raise BilingualVocabularyError("Speed must be between -40% and +40%.")
    if not 0 <= request["english_pause_ms"] <= 3000 or not 0 <= request["pair_pause_ms"] <= 5000:
        raise BilingualVocabularyError("Pauses are outside the allowed range.")
    return pairs


def _ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise RuntimeError("Bilingual vocabulary requires FFmpeg in PATH.")
    return executable


def _create_silence(path: Path, milliseconds: int, control: OperationControl) -> None:
    if milliseconds <= 0:
        return
    result = run_process(
        [
            _ffmpeg(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=24000:cl=mono",
            "-t",
            f"{milliseconds / 1000:.3f}",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            "-y",
            str(path),
        ],
        30,
        control,
    )
    if result.returncode or not path.is_file():
        raise RuntimeError("Cannot create pauses between terms.")


def _concat_audio(paths: list[Path], output_path: Path, control: OperationControl) -> None:
    with tempfile.TemporaryDirectory(dir=AUDIO_DIR, prefix="vocab-") as directory:
        manifest = Path(directory) / "inputs.txt"
        lines = []
        for path in paths:
            escaped_path = path.resolve().as_posix().replace("'", "'\\\\''")
            lines.append(f"file '{escaped_path}'\n")
        manifest.write_text("".join(lines), encoding="utf-8")
        result = run_process(
            [
                _ffmpeg(),
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(manifest),
                "-c:a",
                "libmp3lame",
                "-q:a",
                "4",
                "-y",
                str(output_path),
            ],
            120,
            control,
        )
    if result.returncode or not output_path.is_file():
        raise RuntimeError("Cannot concatenate bilingual audio segments.")


def generate_bilingual_vocabulary_audio(
    request: dict, control: OperationControl | None = None
) -> Path:
    pairs = validate_bilingual_request(request)
    control = control or OperationControl()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_path = unique_path(AUDIO_DIR, make_file_stem(request["title"]), ".mp3")
    temporary_output = output_path.with_name(f"{output_path.stem}.part.mp3")
    fragments: list[Path] = []
    try:
        for index, pair in enumerate(pairs, start=1):
            control.report(f"Vocabular: perechea {index}/{len(pairs)}")
            fragments.append(
                text_to_audio(
                    pair.english,
                    request["english_voice"],
                    request["rate_percent"],
                    file_stem="vocab-en",
                    control=control,
                )
            )
            if request["english_pause_ms"]:
                pause = unique_path(AUDIO_DIR, "vocab-pause", ".mp3")
                _create_silence(pause, request["english_pause_ms"], control)
                fragments.append(pause)
            fragments.append(
                text_to_audio(
                    pair.romanian,
                    request["romanian_voice"],
                    request["rate_percent"],
                    file_stem="vocab-ro",
                    control=control,
                )
            )
            if index < len(pairs) and request["pair_pause_ms"]:
                pause = unique_path(AUDIO_DIR, "vocab-pause", ".mp3")
                _create_silence(pause, request["pair_pause_ms"], control)
                fragments.append(pause)
        control.report("Unire fragmente audio")
        _concat_audio(fragments, temporary_output, control)
        if audio_duration(temporary_output) > MAX_AUDIO_SECONDS:
            raise BilingualVocabularyError("The resulting audio exceeds the 10-minute limit.")
        temporary_output.replace(output_path)
        return output_path
    except BaseException:
        safe_unlink(temporary_output, output_path)
        raise
    finally:
        for fragment in fragments:
            safe_unlink(fragment, fragment.with_suffix(".jsonl"))
