import asyncio
import shutil

from src.app import run_app
from src.config import AUDIO_DIR
from src.db.database import init_db
from src.db.repositories import create_audio_generation, list_audio_generations
from src.services import tts_service
from src.services.operations import run_process
from src.services.storage import media_reference


async def fake_save(text, voice, rate, pitch, output_path, control):
    await asyncio.sleep(2)
    control.check()
    result = run_process(
        [
            shutil.which("ffmpeg"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            str(output_path),
        ],
        30,
        control,
    )
    if result.returncode:
        raise RuntimeError("Test audio generation failed")
    output_path.with_suffix(".jsonl").write_text("", encoding="utf-8")


def setup():
    init_db()
    if not list_audio_generations():
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        path = AUDIO_DIR / "sample.mp3"
        path.write_bytes((bytes.fromhex("fffb90c0") + bytes(413)) * 40)
        for index in range(28):
            create_audio_generation(
                text="This is a saved message.",
                title=f"Exemplu {index}: " + "Titlu lung pentru istoricul mobil " * 3,
                language="Engleza",
                voice_name="Jenny",
                voice_id="en-US-JennyNeural",
                rate_percent=2,
                pitch_hz=0,
                status="completed",
                file_path=media_reference(path),
                file_size_bytes=path.stat().st_size,
                duration_seconds=1.0,
            )
    tts_service._save_audio = fake_save


setup()
run_app()
