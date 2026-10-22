from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from src.config import VIDEO_FPS, VIDEO_HEIGHT, VIDEO_TITLE_DURATION_SECONDS, VIDEO_WIDTH
from src.db.repositories import get_app_settings, save_app_settings


@dataclass(frozen=True)
class RenderSettings:
    video_width: int = VIDEO_WIDTH
    video_height: int = VIDEO_HEIGHT
    video_fps: int = VIDEO_FPS
    title_duration_seconds: float = VIDEO_TITLE_DURATION_SECONDS
    default_rate_percent: int = 0
    default_pitch_hz: int = 0


def current_settings() -> dict[str, int | float]:
    row = get_app_settings()
    if row is None:
        return asdict(RenderSettings())
    return {
        "video_width": row.video_width,
        "video_height": row.video_height,
        "video_fps": row.video_fps,
        "title_duration_seconds": row.title_duration_seconds,
        "default_rate_percent": row.default_rate_percent,
        "default_pitch_hz": row.default_pitch_hz,
    }


def save_settings(values: dict[str, int | float]) -> dict[str, int | float]:
    row = save_app_settings(**values, updated_at=datetime.now(UTC))
    return {
        "video_width": row.video_width,
        "video_height": row.video_height,
        "video_fps": row.video_fps,
        "title_duration_seconds": row.title_duration_seconds,
        "default_rate_percent": row.default_rate_percent,
        "default_pitch_hz": row.default_pitch_hz,
    }
