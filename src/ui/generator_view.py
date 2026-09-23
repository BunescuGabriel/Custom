from pathlib import Path
from uuid import uuid4

import streamlit as st

from src.config import BACKGROUND_DIR, VOICE_OPTIONS
from src.services.generation_service import generate_audio_record
from src.services.text_analyzer import recommend_audio_settings
from src.services.text_preprocessor import make_title
from src.services.video_service import (
    VideoServiceError,
    generate_video_record,
    is_ffmpeg_available,
)


def _init_generator_state() -> None:
    defaults = {
        "is_generating": False,
        "generation_request": None,
        "audio_record": None,
        "generation_error": None,
        "video_record": None,
        "output_format": "MP3",
        "title_input": "",
        "last_auto_title": "",
        "last_title_source_text": "",
        "auto_settings_enabled": True,
        "detected_profile": "story",
        "last_auto_settings_text": "",
        "last_auto_settings_signature": "",
        "language_name": "Rusa",
        "voice_name": "Dmitry",
        "rate_percent": -5,
        "pitch_hz": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _start_generation() -> None:
    language_name = st.session_state.language_name
    voice_name = st.session_state.voice_name

    request = {
        "text": st.session_state.text_input,
        "title": st.session_state.title_input,
        "language": language_name,
        "voice_name": voice_name,
        "voice_id": VOICE_OPTIONS[language_name][voice_name],
        "rate_percent": st.session_state.rate_percent,
        "pitch_hz": st.session_state.pitch_hz,
    }
    if st.session_state.output_format == "MP4":
        background_path = _save_uploaded_background()
        if background_path is None:
            st.session_state.generation_error = (
                "Selecteaza un videoclip de fundal pentru formatul MP4."
            )
            return
        request["background_path"] = str(background_path)

    st.session_state.generation_request = request
    st.session_state.is_generating = True
    st.session_state.audio_record = None
    st.session_state.video_record = None
    st.session_state.generation_error = None


def _save_uploaded_background() -> Path | None:
    uploaded_file = st.session_state.get("background_video")
    if uploaded_file is None:
        return None

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in {".mp4", ".m4v", ".mov", ".webm"}:
        st.session_state.generation_error = (
            "Fundalul trebuie sa fie un fisier video MP4, M4V, MOV sau WebM."
        )
        return None

    BACKGROUND_DIR.mkdir(parents=True, exist_ok=True)
    background_path = BACKGROUND_DIR / f"background-{uuid4().hex}{extension}"
    background_path.write_bytes(uploaded_file.getvalue())
    return background_path


def _update_title_suggestion() -> None:
    text = st.session_state.get("text_input", "")
    if text == st.session_state.last_title_source_text:
        return

    suggested_title = make_title(text)
    current_title = st.session_state.title_input.strip()
    if not current_title or current_title == st.session_state.last_auto_title:
        st.session_state.title_input = suggested_title
    st.session_state.last_auto_title = suggested_title
    st.session_state.last_title_source_text = text


def _apply_auto_settings() -> None:
    text = st.session_state.get("text_input", "")
    cleaned_text = text.strip()
    if not st.session_state.auto_settings_enabled or not cleaned_text:
        return

    recommendation = recommend_audio_settings(cleaned_text)
    signature = (
        f"{cleaned_text}|{recommendation.language_name}|{recommendation.voice_name}|"
        f"{recommendation.profile_name}|{recommendation.rate_percent}|{recommendation.pitch_hz}"
    )

    values_already_applied = (
        st.session_state.language_name == recommendation.language_name
        and st.session_state.voice_name == recommendation.voice_name
        and st.session_state.rate_percent == recommendation.rate_percent
        and st.session_state.pitch_hz == recommendation.pitch_hz
        and st.session_state.detected_profile == recommendation.profile_name
        and st.session_state.last_auto_settings_signature == signature
    )
    if values_already_applied:
        return

    st.session_state.language_name = recommendation.language_name
    st.session_state.voice_name = recommendation.voice_name
    st.session_state.rate_percent = recommendation.rate_percent
    st.session_state.pitch_hz = recommendation.pitch_hz
    st.session_state.detected_profile = recommendation.profile_name
    st.session_state.last_auto_settings_text = cleaned_text
    st.session_state.last_auto_settings_signature = signature


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
        background_path = request.pop("background_path", None)
        audio_record = generate_audio_record(**request)
        st.session_state.audio_record = audio_record
        if background_path is not None:
            st.session_state.video_record = generate_video_record(
                audio_record=audio_record,
                background_path=Path(background_path),
            )
    except VideoServiceError as error:
        st.session_state.generation_error = str(error)
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


def _render_generated_video() -> None:
    video_record = st.session_state.video_record
    if not video_record:
        return

    video_path = Path(video_record.file_path or "")
    if not video_path.is_file():
        st.warning("Videoclipul a fost salvat in istoric, dar fisierul MP4 nu mai exista pe disc.")
        return

    if video_record.generation_seconds is None:
        st.success("Videoclip generat.")
    else:
        st.success(f"Videoclip generat in {video_record.generation_seconds:.2f} secunde.")
    st.video(str(video_path))

    with video_path.open("rb") as video_file:
        st.download_button(
            label="Descarca MP4",
            data=video_file,
            file_name=video_record.file_name or video_path.name,
            mime="video/mp4",
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
            st.radio(
                "Format iesire",
                options=["MP3", "MP4"],
                key="output_format",
                horizontal=True,
                disabled=disabled,
            )
            _update_title_suggestion()
            st.text_input(
                "Titlu",
                key="title_input",
                max_chars=140,
                placeholder="Titlu pentru istoric si numele fisierului...",
                help="Este completat automat din text, dar il poti modifica inainte de generare.",
                disabled=disabled,
            )

            if st.session_state.output_format == "MP4":
                st.file_uploader(
                    "Videoclip de fundal",
                    type=["mp4", "m4v", "mov", "webm"],
                    key="background_video",
                    disabled=disabled,
                    help="Fundalul este adaptat automat la format vertical 1080 x 1920. Audio-ul lui nu este folosit.",
                )
                if not is_ffmpeg_available():
                    st.warning("MP4 necesita FFmpeg si FFprobe instalate in PATH.")

            st.checkbox(
                "Auto settings",
                key="auto_settings_enabled",
                disabled=disabled,
            )
            _apply_auto_settings()

            if (
                st.session_state.auto_settings_enabled
                and st.session_state.get("text_input", "").strip()
            ):
                st.caption(f"Profil detectat: {st.session_state.detected_profile}")

            settings_disabled = disabled or st.session_state.auto_settings_enabled

            st.selectbox(
                "Limba",
                options=list(VOICE_OPTIONS.keys()),
                key="language_name",
                disabled=settings_disabled,
            )

            voice_options = VOICE_OPTIONS[st.session_state.language_name]
            if st.session_state.voice_name not in voice_options:
                st.session_state.voice_name = next(iter(voice_options))

            st.selectbox(
                "Voce",
                options=list(voice_options.keys()),
                key="voice_name",
                disabled=settings_disabled,
            )

            st.slider(
                "Viteza",
                min_value=-40,
                max_value=40,
                step=5,
                format="%d%%",
                key="rate_percent",
                disabled=settings_disabled,
            )

            st.slider(
                "Ton",
                min_value=-20,
                max_value=20,
                step=5,
                format="%d Hz",
                key="pitch_hz",
                disabled=settings_disabled,
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
    _render_generated_video()
