import logging
from pathlib import Path, PureWindowsPath
from uuid import uuid4

from src.config import MEDIA_DIR

logger = logging.getLogger(__name__)


def resolve_media_path(value: str | Path | None) -> Path:
    if not value:
        raise ValueError("Fișierul nu este disponibil.")
    normalized = str(value).replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or PureWindowsPath(normalized).is_absolute():
        try:
            path = path.resolve().relative_to(MEDIA_DIR)
        except ValueError:
            parts = normalized.split("/")
            if "media" not in parts:
                raise ValueError("Fișierul este în afara stocării aplicației.") from None
            path = Path(*parts[len(parts) - parts[::-1].index("media") :])
    resolved = (MEDIA_DIR / path).resolve()
    if not resolved.is_relative_to(MEDIA_DIR) or resolved == MEDIA_DIR:
        raise ValueError("Calea fișierului nu este validă.")
    return resolved


def media_reference(path: Path) -> str:
    return path.resolve().relative_to(MEDIA_DIR).as_posix()


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{Path(stem).name[:80]}-{uuid4().hex}{suffix}"


def safe_unlink(*paths: Path | None) -> None:
    for path in paths:
        if path is not None:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception("artifact_cleanup_failed path=%s", path)
