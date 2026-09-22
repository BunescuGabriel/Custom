from datetime import timezone
from pathlib import Path

import streamlit as st

from src.db.models import AudioGeneration
from src.db.repositories import list_audio_generations


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "necunoscut"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def _format_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "necunoscut"

    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"

    return f"{size_bytes / (1024 * 1024):.2f} MB"


def _format_created_at(row: AudioGeneration) -> str:
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    local_created_at = created_at.astimezone()
    return local_created_at.strftime("%d.%m.%Y %H:%M")


def _format_elapsed(seconds: float | None) -> str:
    if seconds is None:
        return "necunoscut"

    return f"{seconds:.2f} sec"


def _make_text_preview(text: str, max_length: int = 90) -> str:
    preview = " ".join(text.split())
    if len(preview) <= max_length:
        return preview

    return f"{preview[: max_length - 3].rstrip()}..."


def _render_audio_row(row: AudioGeneration) -> None:
    created_at = _format_created_at(row)
    duration = _format_duration(row.duration_seconds)
    preview = _make_text_preview(row.text)
    title = (
        f"#{row.id} - {created_at} - {row.language} - {row.voice_name} " f"- {duration} - {preview}"
    )

    with st.expander(title, expanded=False):
        st.subheader(row.title)

        meta_left, meta_center, meta_right = st.columns([1, 1, 1])
        with meta_left:
            st.write(f"Limba: {row.language}")
            st.write(f"Citit de: {row.voice_name}")
        with meta_right:
            st.write(f"Viteza: {row.rate_percent:+d}%")
            st.write(f"Ton: {row.pitch_hz:+d} Hz")
        with meta_center:
            st.write(f"Creat: {created_at}")
            st.write(f"Durata audio: {duration}")
            st.write(f"Generare: {_format_elapsed(row.generation_seconds)}")

        st.caption(f"Marime: {_format_size(row.file_size_bytes)}")

        if row.status != "completed":
            st.error(row.error_message or "Generarea a esuat.")
            return

        audio_path = Path(row.file_path or "")
        if not audio_path.exists():
            st.warning("Fisierul audio nu mai exista pe disc.")
            return

        st.audio(str(audio_path), format="audio/mp3")

        with audio_path.open("rb") as audio_file:
            st.download_button(
                label="Descarca MP3",
                data=audio_file,
                file_name=row.file_name or audio_path.name,
                mime="audio/mpeg",
                key=f"download_{row.id}",
            )

        st.text_area(
            "Text folosit",
            value=row.text,
            height=180,
            disabled=True,
            key=f"text_{row.id}",
        )


def render_history_view() -> None:
    rows = list_audio_generations(limit=50)
    if not rows:
        st.info("Nu exista inca audio generate.")
        return

    st.caption(f"Ultimele {len(rows)} generari")
    for row in rows:
        _render_audio_row(row)
