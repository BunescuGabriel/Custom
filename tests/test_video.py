import json
import re
import shutil
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from src.db.repositories import create_audio_generation
from src.services import video_service
from src.services.operations import run_process
from src.services.storage import media_reference
from src.services.title_overlay_service import create_title_overlay


def test_long_title_fits_frame(isolated_store):
    path = create_title_overlay("W" * 140)
    with Image.open(path) as image:
        assert image.width <= 1000
        assert image.height <= 1760


def test_render_timeout_removes_partial_file(valid_mp3, monkeypatch):
    monkeypatch.setattr(video_service, "_get_ffmpeg_executable", lambda _: "ffmpeg")
    subtitle = valid_mp3.with_suffix(".ass")
    subtitle.write_text("subtitles")
    overlay = create_title_overlay("Title")

    def timeout(command, *args, **kwargs):
        Path(command[-1]).write_bytes(b"partial")
        raise TimeoutError()

    monkeypatch.setattr(video_service, "run_process", timeout)
    with pytest.raises(TimeoutError):
        video_service._render_video(valid_mp3, valid_mp3, subtitle, overlay, 1, intro_seconds=0)
    assert not list(video_service.VIDEO_DIR.glob("*.mp4"))


@pytest.mark.integration
@pytest.mark.parametrize("dimensions,crop", [("640x360", "left"), ("180x320", "center")])
def test_real_mp4_with_short_background(isolated_store, audio_parameters, dimensions, crop):
    if not video_service.is_ffmpeg_available():
        pytest.skip("FFmpeg and FFprobe are required")
    audio_path = isolated_store / "audio" / "tone.mp3"
    audio_path.parent.mkdir()
    background = isolated_store / "backgrounds" / "short.mp4"
    background.parent.mkdir()
    ffmpeg = shutil.which("ffmpeg")
    assert (
        run_process(
            [
                ffmpeg,
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=1",
                str(audio_path),
            ],
            30,
        ).returncode
        == 0
    )
    assert (
        run_process(
            [
                ffmpeg,
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={dimensions}:rate=30",
                "-t",
                "0.5",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(background),
            ],
            30,
        ).returncode
        == 0
    )
    audio = create_audio_generation(
        **audio_parameters, file_path=media_reference(audio_path), status="completed"
    )
    video = video_service.generate_video_record(
        audio_record=audio,
        background_path=background,
        intro_seconds=1,
        crop_position=crop,
        allow_approximate=True,
    )
    output = isolated_store / video.file_path
    result = run_process(
        [
            shutil.which("ffprobe"),
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(output),
        ],
        30,
    )
    metadata = json.loads(result.stdout)
    streams = {stream["codec_type"]: stream for stream in metadata["streams"]}
    assert streams["video"]["width"] == 1080 and streams["video"]["height"] == 1920
    assert streams["video"]["pix_fmt"] == "yuv420p"
    assert streams["audio"]["codec_name"] == "aac"
    assert 1.9 <= float(metadata["format"]["duration"]) <= 2.3
    assert video.subtitle_quality == "approximate"
    assert not list(isolated_store.rglob("*.part.*"))
    samples = []
    for index, timestamp in enumerate((0.05, 0.8, 1.0)):
        frame = isolated_store / f"sample-{index}.png"
        result = run_process(
            [
                ffmpeg,
                "-v",
                "error",
                "-ss",
                str(timestamp),
                "-i",
                str(output),
                "-frames:v",
                "1",
                str(frame),
            ],
            30,
        )
        assert result.returncode == 0
        with Image.open(frame) as image:
            samples.append(image.convert("RGB").crop((0, 0, 1080, 180)))
    assert max(ImageStat.Stat(ImageChops.difference(samples[0], samples[1])).mean) < 5
    source_start = isolated_store / "source-start.png"
    result = run_process(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(background),
            "-vf",
            video_service._crop_filter(crop),
            "-frames:v",
            "1",
            str(source_start),
        ],
        30,
    )
    assert result.returncode == 0
    with Image.open(source_start) as image:
        reference = image.convert("RGB").crop((0, 0, 1080, 180))
        assert max(ImageStat.Stat(ImageChops.difference(reference, samples[2])).mean) < 8
    for timestamp, silent in ((0.1, True), (1.2, False)):
        result = run_process(
            [
                ffmpeg,
                "-hide_banner",
                "-ss",
                str(timestamp),
                "-i",
                str(output),
                "-t",
                "0.3",
                "-vn",
                "-af",
                "volumedetect",
                "-f",
                "null",
                "-",
            ],
            30,
        )
        volume = float(re.search(r"max_volume: ([\d.\-]+) dB", result.stderr).group(1))
        assert (volume < -60) == silent
