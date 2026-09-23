from datetime import UTC
from pathlib import Path

import streamlit as st

from src.db.models import VideoGeneration
from src.db.repositories import list_video_generations


def _format_created_at(row: VideoGeneration) -> str:
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return created_at.astimezone().strftime("%d.%m.%Y %H:%M")


def _format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "necunoscut"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def _format_elapsed(seconds: float | None) -> str:
    if seconds is None:
        return "necunoscut"

    return f"{seconds:.2f} sec"


def _format_size(size_bytes: int | None) -> str:
    if size_bytes is None:
        return "necunoscut"

    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.0f} KB"

    return f"{size_bytes / (1024 * 1024):.2f} MB"


def _format_status(status: str) -> str:
    return {"completed": "✅ Succes", "failed": "❌ Fail"}.get(status, status)


def _make_file_preview(file_path: str, max_length: int = 42) -> str:
    file_name = Path(file_path).name
    if len(file_name) <= max_length:
        return file_name
    return f"{file_name[: max_length - 3].rstrip()}..."


def _get_title(row: VideoGeneration) -> str:
    return row.audio_generation.title


def _render_video_details(row: VideoGeneration) -> None:
    with st.container(border=True):
        st.subheader(f"#{row.id} - {_get_title(row)}")

        if row.status == "failed":
            st.error(row.error_message or "Generarea videoclipului a esuat.")
            return

        video_path = Path(row.file_path or "")
        if not video_path.is_file():
            st.warning("Fisierul MP4 nu mai exista pe disc.")
            return

        st.video(str(video_path))
        with video_path.open("rb") as video_file:
            st.download_button(
                "Descarca MP4",
                data=video_file,
                file_name=row.file_name or video_path.name,
                mime="video/mp4",
                key=f"video_download_{row.id}",
            )


def _select_history_row(editor_key: str, row_ids: list[int]) -> None:
    edits = st.session_state[editor_key]["edited_rows"]
    for row_index, changes in edits.items():
        if "Selecteaza" not in changes:
            continue
        row_id = row_ids[int(row_index)]
        if changes["Selecteaza"]:
            st.session_state.video_history_selected_id = row_id
        elif st.session_state.get("video_history_selected_id") == row_id:
            st.session_state.video_history_selected_id = None
    st.session_state.video_history_selection_version = (
        st.session_state.get("video_history_selection_version", 0) + 1
    )


def render_video_history_view() -> None:
    rows = list_video_generations(limit=50)
    if not rows:
        st.info("Nu exista inca videoclipuri generate.")
        return

    st.caption(f"Ultimele {len(rows)} videoclipuri")
    selected_id = st.session_state.get("video_history_selected_id")
    table_rows = [
        {
            "Selecteaza": row.id == selected_id,
            "Titlu": _get_title(row),
            "Status": _format_status(row.status),
            "Creat": _format_created_at(row),
            "Durata video": _format_duration(row.duration_seconds),
            "Generare": _format_elapsed(row.generation_seconds),
            "Marime": _format_size(row.file_size_bytes),
        }
        for row in rows
    ]
    selection_version = st.session_state.get("video_history_selection_version", 0)
    editor_key = f"video_history_table_{selection_version}"
    st.data_editor(
        table_rows,
        column_config={
            "Selecteaza": st.column_config.CheckboxColumn(
                "Selecteaza",
                help="Bifeaza pentru a deschide videoclipul sau detaliile erorii.",
                width="medium",
                default=False,
            ),
            "Titlu": st.column_config.TextColumn("Titlu", width="medium"),
            "Status": st.column_config.TextColumn("Status", width="small"),
            "Creat": st.column_config.TextColumn("Creat", width="medium"),
        },
        hide_index=True,
        use_container_width=True,
        disabled=[column for column in table_rows[0] if column != "Selecteaza"],
        on_change=_select_history_row,
        args=(editor_key, [row.id for row in rows]),
        key=editor_key,
    )
    selected_row = next((row for row in rows if row.id == selected_id), None)
    if selected_row is not None:
        _render_video_details(selected_row)
    else:
        st.caption("Bifeaza coloana Selecteaza pentru a vedea videoclipul sau detaliile erorii.")
