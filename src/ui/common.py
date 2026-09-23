from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from src.config import MAX_DOWNLOAD_BYTES
from src.services.operations import describe_error
from src.services.storage import resolve_media_path
from src.ui.labels import LANGUAGE_LABELS, STATUS_LABELS


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def format_size(size: int | None) -> str:
    return "necunoscut" if size is None else f"{size / 1024 ** 2:.2f} MB"


@st.cache_data(max_entries=4, ttl=300, show_spinner=False)
def _file_bytes(path: str, modified: int, size: int) -> bytes:
    return Path(path).read_bytes()


def render_media(record, kind: str, key: str) -> None:
    if record.status != "completed":
        if record.error_message:
            st.error(record.error_message)
        else:
            st.info(STATUS_LABELS.get(record.status, record.status))
        return
    try:
        path = resolve_media_path(record.file_path)
        if not path.is_file():
            st.warning("Fișierul nu mai există pe disc.")
            return
        info = path.stat()
        if info.st_size > MAX_DOWNLOAD_BYTES:
            st.info(
                "Fișier mare: deschide-l din dosarul local pentru a evita încărcarea în memoria browserului."
            )
            st.code(str(path), language=None)
            return
        data = _file_bytes(str(path), info.st_mtime_ns, info.st_size)
        if kind == "audio":
            st.audio(data, format="audio/mpeg")
        else:
            st.video(data)
        st.download_button(
            "Descarcă MP3" if kind == "audio" else "Descarcă MP4",
            data,
            file_name=record.file_name or path.name,
            mime="audio/mpeg" if kind == "audio" else "video/mp4",
            key=key,
        )
    except (OSError, ValueError) as error:
        st.warning(describe_error(error))


def audio_parameters(row) -> dict:
    return {
        key: getattr(row, key)
        for key in (
            "text",
            "title",
            "language",
            "voice_name",
            "voice_id",
            "rate_percent",
            "pitch_hz",
        )
    }


def restore_audio(row, output_format: str = "MP3", video=None) -> None:
    st.session_state["restore_request"] = {
        "audio": audio_parameters(row),
        "audio_generation_id": row.id if row.status == "completed" else None,
        "output_format": output_format,
        "background_path": video.background_path if video else None,
        "intro_seconds": video.intro_seconds if video else 3.0,
        "crop_position": video.crop_position if video else "center",
        "allow_approximate": bool(video and video.subtitle_quality == "approximate"),
    }
    st.session_state["navigation"] = "Generator"


def render_snapshot(row) -> None:
    st.markdown(f"**{row.title}**")
    st.caption(
        f"{LANGUAGE_LABELS.get(row.language, row.language)} · {row.voice_name} · viteză {row.rate_percent:+d}% · ton {row.pitch_hz:+d} Hz"
    )
    with st.expander("Textul acestui rezultat"):
        st.text(row.text)
