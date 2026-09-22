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


def _format_status(status: str) -> str:
    return {"completed": "✅ Succes", "failed": "❌ Fail"}.get(status, status)


def _render_audio_details(row: AudioGeneration) -> None:
    with st.container(border=True):
        st.subheader(f"#{row.id} - {row.title}")

        if row.status == "failed":
            st.error(row.error_message or "Generarea a esuat.")
        elif row.status == "completed":
            audio_path = Path(row.file_path or "")
            if not audio_path.is_file():
                st.warning("Fisierul audio nu mai exista pe disc.")
            else:
                st.audio(str(audio_path), format="audio/mp3")

                with audio_path.open("rb") as audio_file:
                    st.download_button(
                        label="Descarca MP3",
                        data=audio_file,
                        file_name=row.file_name or audio_path.name,
                        mime="audio/mpeg",
                        key=f"download_{row.id}",
                    )
        else:
            st.info(f"Status: {_format_status(row.status)}")

        st.text_area(
            "Text folosit",
            value=row.text,
            height=180,
            disabled=True,
            key=f"text_{row.id}",
        )


def _select_history_row(editor_key: str, row_ids: list[int]) -> None:
    edits = st.session_state[editor_key]["edited_rows"]
    for row_index, changes in edits.items():
        if "Selecteaza" not in changes:
            continue
        row_id = row_ids[int(row_index)]
        if changes["Selecteaza"]:
            st.session_state.history_selected_id = row_id
        elif st.session_state.get("history_selected_id") == row_id:
            st.session_state.history_selected_id = None
    st.session_state.history_selection_version = (
        st.session_state.get("history_selection_version", 0) + 1
    )


def render_history_view() -> None:
    rows = list_audio_generations(limit=50)
    if not rows:
        st.info("Nu exista inca audio generate.")
        return

    st.caption(f"Ultimele {len(rows)} generari")
    selected_id = st.session_state.get("history_selected_id")
    table_rows = [
        {
            "Selecteaza": row.id == selected_id,
            # "ID": row.id,
            "Title": _make_text_preview(row.title),
            "Status": _format_status(row.status),
            "Creat": _format_created_at(row),
            "Limba": row.language,
            "Voce": row.voice_name,
            "Durata audio": _format_duration(row.duration_seconds),
            "Generare": _format_elapsed(row.generation_seconds),
            "Marime": _format_size(row.file_size_bytes),
            "Viteza": f"{row.rate_percent:+d}%",
            "Ton": f"{row.pitch_hz:+d} Hz",
        }
        for row in rows
    ]
    selection_version = st.session_state.get("history_selection_version", 0)
    editor_key = f"audio_history_table_{selection_version}"
    st.data_editor(
        table_rows,
        column_config={
            "Selecteaza": st.column_config.CheckboxColumn(
                "Selectează",
                help="Bifeaza pentru a deschide detaliile. Poti selecta un singur rand.",
                width="medium",
                default=False,
            ),
            "Title": st.column_config.TextColumn("Title", width="medium"),
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
        _render_audio_details(selected_row)
    else:
        st.caption("Bifeaza coloana Selecteaza pentru textul complet, audio sau detaliile erorii.")
