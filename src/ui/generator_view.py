from pathlib import Path

import streamlit as st

from src.config import VOICE_OPTIONS
from src.services.generation_service import generate_audio_record


def _init_generator_state() -> None:
    defaults = {
        "is_generating": False,
        "generation_request": None,
        "audio_record": None,
        "generation_error": None,
        "language_name": "Rusa",
        "voice_name": "Svetlana",
        "rate_percent": -5,
        "pitch_hz": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _start_generation() -> None:
    language_name = st.session_state.language_name
    voice_name = st.session_state.voice_name

    st.session_state.generation_request = {
        "text": st.session_state.text_input,
        "language": language_name,
        "voice_name": voice_name,
        "voice_id": VOICE_OPTIONS[language_name][voice_name],
        "rate_percent": st.session_state.rate_percent,
        "pitch_hz": st.session_state.pitch_hz,
    }
    st.session_state.is_generating = True
    st.session_state.audio_record = None
    st.session_state.generation_error = None


def _render_generation_status() -> None:
    st.markdown(
        """
        <div class="generation-panel">
            <div class="generation-spinner"></div>
            <div>
                <div class="generation-title">Se genereaza audio...</div>
                <div class="generation-text">Controalele sunt blocate pana se termina procesarea.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _process_generation() -> None:
    request = st.session_state.generation_request
    if not request:
        return

    try:
        st.session_state.audio_record = generate_audio_record(**request)
    except ValueError as error:
        st.session_state.generation_error = str(error)
    except Exception as error:
        st.session_state.generation_error = f"Nu am putut genera audio-ul: {error}"
    finally:
        st.session_state.generation_request = None
        st.session_state.is_generating = False
        st.rerun()


def _render_generated_audio() -> None:
    audio_record = st.session_state.audio_record
    if not audio_record:
        return

    audio_path = Path(audio_record.file_path or "")
    if not audio_path.exists():
        st.warning("Audio-ul a fost salvat in istoric, dar fisierul MP3 nu mai exista pe disc.")
        return

    if audio_record.generation_seconds is None:
        st.success("Audio generat.")
    else:
        st.success(f"Audio generat in {audio_record.generation_seconds:.2f} secunde.")
    st.audio(str(audio_path), format="audio/mp3")

    with audio_path.open("rb") as audio_file:
        st.download_button(
            label="Descarca MP3",
            data=audio_file,
            file_name=audio_record.file_name or audio_path.name,
            mime="audio/mpeg",
        )


def render_generator_view() -> None:
    _init_generator_state()

    disabled = st.session_state.is_generating
    if disabled:
        _render_generation_status()

    with st.container(border=True):
        left_column, right_column = st.columns([1.65, 1], gap="large")

        with left_column:
            st.text_area(
                "Text",
                key="text_input",
                height=360,
                placeholder="Scrie textul pe care vrei sa il transformi in audio...",
                disabled=disabled,
            )

        with right_column:
            st.selectbox(
                "Limba",
                options=list(VOICE_OPTIONS.keys()),
                key="language_name",
                disabled=disabled,
            )

            voice_options = VOICE_OPTIONS[st.session_state.language_name]
            if st.session_state.voice_name not in voice_options:
                st.session_state.voice_name = next(iter(voice_options))

            st.selectbox(
                "Voce",
                options=list(voice_options.keys()),
                key="voice_name",
                disabled=disabled,
            )

            st.slider(
                "Viteza",
                min_value=-40,
                max_value=40,
                step=5,
                format="%d%%",
                key="rate_percent",
                disabled=disabled,
            )

            st.slider(
                "Ton",
                min_value=-20,
                max_value=20,
                step=5,
                format="%d Hz",
                key="pitch_hz",
                disabled=disabled,
            )

            st.button(
                "Genereaza audio",
                type="primary",
                disabled=disabled,
                on_click=_start_generation,
            )

    if st.session_state.is_generating:
        _process_generation()

    if st.session_state.generation_error:
        st.error(st.session_state.generation_error)

    _render_generated_audio()
