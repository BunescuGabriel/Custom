import streamlit as st

from src.db.models import AudioGeneration, VideoGeneration
from src.db.repositories import get_record, list_audio_generations, list_video_generations
from src.services.media_service import delete_generation
from src.services.operations import describe_error
from src.ui.common import as_utc, format_size, render_media, render_snapshot, restore_audio
from src.ui.labels import STATUS_LABELS


def _title(row) -> str:
    if isinstance(row, AudioGeneration):
        return row.title
    return row.audio_generation.title if row.audio_generation else "Audio asociat indisponibil"


def _reset_page(prefix: str) -> None:
    st.session_state[f"{prefix}_page"] = 1


def _delete(kind: str, record_id: int) -> None:
    try:
        delete_generation(kind, record_id)
        st.session_state[f"{kind}_selected"] = None
        st.session_state[f"{kind}_message"] = "Înregistrarea a fost ștearsă."
    except Exception as error:
        st.session_state[f"{kind}_message"] = describe_error(error)


def render_history(kind: str) -> None:
    is_audio = kind == "audio"
    st.subheader("Istoric audio" if is_audio else "Istoric video")
    search = st.text_input(
        "Caută după titlu", key=f"{kind}_search", on_change=_reset_page, args=(kind,)
    )
    status = st.selectbox(
        "Stare",
        [""] + list(STATUS_LABELS),
        format_func=lambda value: STATUS_LABELS.get(value, "Toate"),
        key=f"{kind}_status",
        on_change=_reset_page,
        args=(kind,),
    )
    page = int(st.number_input("Pagina", min_value=1, step=1, key=f"{kind}_page"))
    loader = list_audio_generations if is_audio else list_video_generations
    rows = loader(limit=26, offset=(page - 1) * 25, search=search, status=status)
    has_next = len(rows) > 25
    rows = rows[:25]
    st.caption(
        f"Pagina {page} · {len(rows)} rezultate · date în UTC"
        + (" · există pagina următoare" if has_next else "")
    )
    if st.session_state.get(f"{kind}_message"):
        st.info(st.session_state.pop(f"{kind}_message"))
    if not rows:
        st.info("Nicio înregistrare pe această pagină. Modifică pagina sau filtrele.")
    if rows and st.checkbox("Arată tabelul cu sortare", key=f"{kind}_table"):
        table = []
        for row in rows:
            values = {
                "ID": row.id,
                "Titlu": _title(row),
                "Stare": STATUS_LABELS.get(row.status, row.status),
                "Creat (UTC)": as_utc(row.created_at),
                "Durată (s)": row.duration_seconds,
                "Procesare (s)": row.generation_seconds,
                "Dimensiune (MB)": (
                    None if row.file_size_bytes is None else row.file_size_bytes / 1024**2
                ),
            }
            if is_audio:
                values.update(
                    {
                        "Voce": row.voice_name,
                        "Viteză (%)": row.rate_percent,
                        "Ton (Hz)": row.pitch_hz,
                    }
                )
            table.append(values)
        st.dataframe(
            table,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Creat (UTC)": st.column_config.DatetimeColumn(format="YYYY-MM-DD HH:mm:ss"),
                "Durată (s)": st.column_config.NumberColumn(format="%.2f"),
                "Procesare (s)": st.column_config.NumberColumn(format="%.2f"),
                "Dimensiune (MB)": st.column_config.NumberColumn(format="%.2f"),
            },
        )
    model = AudioGeneration if is_audio else VideoGeneration
    selected = st.session_state.get(f"{kind}_selected")
    lookup = {row.id: row for row in rows}
    if selected and selected not in lookup:
        previous = get_record(model, selected)
        if previous is not None:
            lookup[selected] = previous
        else:
            st.session_state[f"{kind}_selected"] = None
    selected = st.selectbox(
        "Deschide înregistrarea",
        [None] + list(lookup),
        format_func=lambda value: (
            "Alege un rezultat"
            if value is None
            else f"#{value} · {_title(lookup[value])[:120]} · {STATUS_LABELS.get(lookup[value].status, lookup[value].status)}"
        ),
        key=f"{kind}_selected",
    )
    if selected is None:
        return
    row = lookup[selected]
    st.caption(
        f"Creat: {as_utc(row.created_at):%Y-%m-%d %H:%M:%S} UTC · {format_size(row.file_size_bytes)}"
    )
    audio = row if is_audio else row.audio_generation
    if audio:
        render_snapshot(audio)
        st.button(
            "Repetă / editează",
            key=f"edit_{kind}_{row.id}",
            on_click=restore_audio,
            args=(audio, "MP3"),
        )
        st.button(
            "Creează video din acest audio" if is_audio else "Repetă videoclipul",
            key=f"video_{kind}_{row.id}",
            on_click=restore_audio,
            args=(audio, "MP4", None if is_audio else row),
            disabled=audio.status != "completed",
        )
    else:
        st.warning("Legătura către audio este deteriorată. Celelalte rezultate rămân accesibile.")
    if not is_audio:
        st.caption(
            f"Audio #{row.audio_generation_id} · Fundal: {row.background_path} · Introducere: {row.intro_seconds:g} s"
        )
        if row.subtitle_quality == "approximate":
            st.warning("Subtitrări aproximative.")
        if audio and st.checkbox("Arată audio-ul asociat", key=f"linked_audio_{row.id}"):
            render_media(audio, "audio", f"linked_download_{row.id}")
    elif row.cache_hit:
        st.caption("Audio reutilizat din cache.")
    render_media(row, kind, f"history_download_{kind}_{row.id}")
    confirm = st.checkbox(
        "Confirm ștergerea acestei înregistrări și a fișierelor nepartajate",
        key=f"delete_confirm_{kind}_{row.id}",
    )
    st.button(
        "Șterge",
        key=f"delete_{kind}_{row.id}",
        disabled=not confirm or st.session_state.get("generation_busy", False),
        on_click=_delete,
        args=(kind, row.id),
    )
