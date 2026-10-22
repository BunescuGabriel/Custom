import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key and not key.startswith("#"):
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / ".env")
SETTINGS = json.loads((BASE_DIR / "config" / "settings.json").read_text(encoding="utf-8"))

configured_media_dir = os.environ.get("APP_MEDIA_DIR")
MEDIA_DIR = Path(configured_media_dir or BASE_DIR / "media").resolve()
DATA_DIR = MEDIA_DIR / "data"
AUDIO_DIR = MEDIA_DIR / "audio"
BACKGROUND_DIR = MEDIA_DIR / "backgrounds"
VIDEO_DIR = MEDIA_DIR / "videos"
SUBTITLE_DIR = VIDEO_DIR / "subtitles"
TITLE_OVERLAY_DIR = VIDEO_DIR / "title_overlays"
LOG_DIR = DATA_DIR
DATABASE_PATH = DATA_DIR / "app.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH.as_posix()}"

TTS_TIMEOUT_SECONDS = SETTINGS["tts_timeout_seconds"]
TTS_MAX_ATTEMPTS = SETTINGS["tts_max_attempts"]
TTS_RETRY_DELAY_SECONDS = SETTINGS["tts_retry_delay_seconds"]
VIDEO_WIDTH = SETTINGS["video_width"]
VIDEO_HEIGHT = SETTINGS["video_height"]
VIDEO_FPS = SETTINGS["video_fps"]
VIDEO_TITLE_DURATION_SECONDS = SETTINGS["video_title_duration_seconds"]
VIDEO_TITLE_PREVIEW_SECONDS = SETTINGS["video_title_preview_seconds"]
VIDEO_TITLE_FONT_PATH = os.environ.get("VIDEO_TITLE_FONT_PATH", "")
VIDEO_TITLE_FONT_SIZE = SETTINGS["video_title_font_size"]
VIDEO_TITLE_MIN_FONT_SIZE = SETTINGS["video_title_min_font_size"]
VIDEO_TITLE_MAX_LINES = SETTINGS["video_title_max_lines"]
VIDEO_TITLE_MAX_TEXT_WIDTH = SETTINGS["video_title_max_text_width"]
VIDEO_RENDER_TIMEOUT_SECONDS = SETTINGS["video_render_timeout_seconds"]
MAX_TEXT_CHARACTERS = SETTINGS["max_text_characters"]
MAX_AUDIO_SECONDS = SETTINGS["max_audio_seconds"]
MAX_UPLOAD_BYTES = SETTINGS["max_upload_bytes"]
MAX_VIDEO_PIXELS = SETTINGS["max_video_pixels"]
MAX_BACKGROUND_SECONDS = SETTINGS["max_background_seconds"]
AUDIO_PROFILES = SETTINGS["audio_profiles"]
VOICE_OPTIONS = SETTINGS["voice_options"]
