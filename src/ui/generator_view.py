import hashlib
import html
import json
from datetime import UTC, datetime

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from src.config import (
    AUDIO_PROFILES,
    MAX_TEXT_CHARACTERS,
    VIDEO_TITLE_DURATION_SECONDS,
    VOICE_OPTIONS,
)
from src.db.models import AudioGeneration, GenerationJob, VideoGeneration
from src.db.repositories import get_record
from src.services.form_service import estimate_seconds, normalize_form, validate_request
from src.services.job_service import ACTIVE_STATUSES, cancel_job, submit_job
from src.services.media_service import save_background
from src.services.operations import describe_error
from src.services.storage import media_reference, resolve_media_path, safe_unlink
from src.services.text_preprocessor import clean_text
from src.services.title_overlay_service import (
    _make_title_layout,
    create_title_overlay,
    resolve_font,
)
from src.services.video_service import extract_preview, validate_video_tools
from src.ui.common import as_utc, render_media, render_snapshot
from src.ui.labels import CROP_LABELS, LANGUAGE_LABELS, STATUS_LABELS


def _init_generator_state() -> None:
    defaults = {
        "text_input": "",
        "title_input": "",
        "last_auto_title": "",
        "last_title_source_text": "",
        "auto_settings_enabled": True,
        "language_name": "Romana",
        "voice_name": "Alina",
        "rate_percent": 0,
        "pitch_hz": 0,
        "output_format": "MP3",
        "generation_error": None,
        "active_job_id": None,
        "intro_seconds": VIDEO_TITLE_DURATION_SECONDS,
        "crop_position": "center",
        "allow_approximate": False,
        "force_synthesis": False,
    }
    draft = st.session_state.get("generator_draft", {})
    for key, value in defaults.items():
        current = st.session_state.get(key, draft.get(key, value))
        st.session_state[key] = value if current is None else current
    restored = st.session_state.pop("restore_request", None)
    if restored:
        audio = restored["audio"]
        st.session_state.update(
            {
                "text_input": audio["text"],
                "title_input": audio["title"],
                "language_name": audio["language"],
                "voice_name": audio["voice_name"],
                "rate_percent": audio["rate_percent"],
                "pitch_hz": audio["pitch_hz"],
                "auto_settings_enabled": False,
                "output_format": restored["output_format"],
                "reuse_audio_id": restored.get("audio_generation_id"),
                "reuse_audio_snapshot": audio,
                "reuse_background_path": restored.get("background_path"),
                "intro_seconds": round(
                    restored.get("intro_seconds", VIDEO_TITLE_DURATION_SECONDS) * 2
                )
                / 2,
                "crop_position": restored.get("crop_position", "center"),
                "allow_approximate": restored.get("allow_approximate", False),
            }
        )
        st.session_state.pop("background_video", None)
        st.session_state.pop("background_upload", None)
    query_job = st.query_params.get("job")
    if query_job and not st.session_state.active_job_id:
        st.session_state.active_job_id = query_job


def _save_uploaded_background():
    uploaded = st.session_state.get("background_upload") or st.session_state.get("background_video")
    if uploaded is None:
        reused = st.session_state.get("reuse_background_path")
        if reused:
            return resolve_media_path(reused)
        raise ValueError("Selectează un videoclip de fundal pentru MP4.")
    data = uploaded.getvalue()
    signature = hashlib.sha256(data).hexdigest()
    cached = st.session_state.get("prepared_background")
    if cached and cached[0] == signature:
        path = resolve_media_path(cached[1])
        if path.is_file():
            return path
    path = save_background(uploaded.name, data)
    st.session_state.prepared_background = (signature, media_reference(path))
    return path


def _start_generation() -> None:
    try:
        audio = normalize_form(st.session_state)
        validate_request(audio)
        parameters = {
            "audio": audio,
            "output_format": st.session_state.output_format,
            "force_synthesis": st.session_state.get("force_synthesis", False),
        }
        if st.session_state.output_format == "MP4":
            validate_video_tools()
            _make_title_layout(audio["title"])
            background = _save_uploaded_background()
            parameters.update(
                background_path=media_reference(background),
                intro_seconds=float(st.session_state.intro_seconds),
                crop_position=st.session_state.crop_position,
                allow_approximate=st.session_state.allow_approximate,
            )
            if (
                not parameters["force_synthesis"]
                and st.session_state.get("reuse_audio_snapshot") == audio
                and st.session_state.get("reuse_audio_id")
            ):
                parameters["audio_generation_id"] = st.session_state.reuse_audio_id
        job_id = submit_job(parameters)
        st.session_state.active_job_id = job_id
        st.session_state.generation_error = None
        st.query_params["job"] = job_id
    except Exception as error:
        st.session_state.generation_error = describe_error(error)


def _render_preview() -> None:
    frame = title = None
    try:
        background = _save_uploaded_background()
        frame = extract_preview(background, st.session_state.crop_position)
        title = create_title_overlay(st.session_state.title_input)
        with Image.open(frame) as source:
            preview = source.convert("RGBA")
        with Image.open(title) as overlay:
            if st.session_state.intro_seconds > 0:
                preview.alpha_composite(
                    overlay,
                    ((preview.width - overlay.width) // 2, (preview.height - overlay.height) // 2),
                )
        draw = ImageDraw.Draw(preview)
        draw.text(
            (90, preview.height - 360),
            "Poziția subtitrărilor",
            font=ImageFont.truetype(resolve_font(), 54),
            fill="white",
            stroke_width=3,
            stroke_fill="black",
        )
        st.image(
            preview,
            caption="Încadrarea 9:16. Titlul apare în introducere; subtitrările în timpul narațiunii.",
            width=270,
        )
    except Exception as error:
        st.warning(describe_error(error))
    finally:
        safe_unlink(frame, title)


def _render_job() -> None:
    job_id = st.session_state.get("active_job_id")
    if not job_id:
        return
    job = get_record(GenerationJob, job_id)
    if job is None:
        st.warning("Lucrarea nu mai există.")
        return
    active = job.status in ACTIVE_STATUSES
    previous = st.session_state.get("job_was_active")
    st.session_state.job_was_active = active
    if previous is True and not active:
        st.rerun()
    elapsed = (
        (datetime.now(UTC) if active else as_utc(job.updated_at)) - as_utc(job.created_at)
    ).total_seconds()
    st.markdown(
        f'<div class="generation-panel" role="status" aria-live="polite" aria-atomic="true">'
        f"<strong>{html.escape(job.stage)}</strong> · {elapsed:.0f} secunde</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Lucrare: {job.id} · {STATUS_LABELS.get(job.status, job.status)}")
    if active:
        st.button(
            "Anulează generarea",
            key=f"cancel_{job.id}",
            on_click=cancel_job,
            args=(job.id,),
            disabled=job.cancel_requested,
        )
        if job.cancel_requested:
            st.info("Anularea este în curs.")
    if job.error_message:
        st.error(job.error_message)
    parameters = json.loads(job.parameters)
    current = {
        "text": clean_text(st.session_state.get("text_input", "")),
        "title": st.session_state.get("title_input", ""),
        "language": st.session_state.get("language_name"),
        "voice_name": st.session_state.get("voice_name"),
        "rate_percent": st.session_state.get("rate_percent"),
        "pitch_hz": st.session_state.get("pitch_hz"),
    }
    if any(
        parameters["audio"].get(key) != value for key, value in current.items()
    ) or parameters.get("output_format") != st.session_state.get("output_format"):
        st.info(
            "Formularul s-a schimbat. Rezultatul de mai jos aparține parametrilor salvați cu această lucrare."
        )
    if job.audio_generation_id:
        audio = get_record(AudioGeneration, job.audio_generation_id)
        if audio and audio.status == "completed":
            render_snapshot(audio)
            st.caption(
                "Audio reutilizat din cache."
                if audio.cache_hit
                else f"Sinteză audio: {audio.generation_seconds or 0:.2f} secunde."
            )
            render_media(audio, "audio", f"result_audio_{job.id}")
    if job.video_generation_id:
        video = get_record(VideoGeneration, job.video_generation_id)
        if video and video.status == "completed":
            st.caption(
                f"MP4 · introducere {video.intro_seconds:g} s · decupare {CROP_LABELS[video.crop_position]}"
            )
            if video.subtitle_quality == "approximate":
                st.warning("Subtitrările sunt aproximative și pot diferi de ritmul vorbirii.")
            render_media(video, "video", f"result_video_{job.id}")


def _reset_recommendation() -> None:
    st.session_state.pop("last_recommendation_text", None)


def _remember_upload() -> None:
    st.session_state.background_upload = st.session_state.get("background_video")
    st.session_state.pop("reuse_background_path", None)


def render_generator_view() -> None:
    _init_generator_state()
    normalize_form(st.session_state)
    job = (
        get_record(GenerationJob, st.session_state.active_job_id)
        if st.session_state.active_job_id
        else None
    )
    disabled = bool(job and job.status in ACTIVE_STATUSES)
    st.caption(
        "Sinteza nouă trimite textul serviciului Microsoft Edge prin edge-tts și necesită internet. Textul și fișierele rămân local până le ștergi din istoric."
    )
    st.text_area(
        "Text", key="text_input", height=300, max_chars=MAX_TEXT_CHARACTERS, disabled=disabled
    )
    st.text_input("Titlu", key="title_input", max_chars=140, disabled=disabled)
    st.radio(
        "Format de ieșire", ["MP3", "MP4"], key="output_format", horizontal=True, disabled=disabled
    )
    st.checkbox(
        "Recomandări automate la schimbarea textului",
        key="auto_settings_enabled",
        disabled=disabled,
        on_change=_reset_recommendation,
    )
    if (
        st.session_state.get("language_warning")
        and st.session_state.auto_settings_enabled
        and st.session_state.text_input
    ):
        st.warning(st.session_state.language_warning)
    profile = st.session_state.get("detected_profile")
    if profile:
        st.caption(
            f"Profil recomandat: {AUDIO_PROFILES[profile]['label']}. Poți modifica orice setare."
        )
    st.selectbox(
        "Limba",
        list(VOICE_OPTIONS),
        key="language_name",
        format_func=LANGUAGE_LABELS.get,
        disabled=disabled,
    )
    st.selectbox(
        "Voce",
        list(VOICE_OPTIONS[st.session_state.language_name]),
        key="voice_name",
        disabled=disabled,
    )
    st.slider("Viteză", -40, 40, step=1, format="%d%%", key="rate_percent", disabled=disabled)
    st.slider("Ton", -20, 20, step=1, format="%d Hz", key="pitch_hz", disabled=disabled)
    st.checkbox(
        "Ignoră cache-ul și sintetizează din nou",
        key="force_synthesis",
        disabled=disabled,
        help="Util pentru a reface timpii cuvintelor unui MP3 vechi.",
    )
    seconds = estimate_seconds(st.session_state.text_input, st.session_state.rate_percent)
    st.caption(
        f"Durată estimată: {seconds:.0f} secunde. Limită: 10 minute / {MAX_TEXT_CHARACTERS} caractere."
    )
    ready = bool(st.session_state.text_input.strip()) and seconds <= 600
    if st.session_state.get("generation_busy") and not disabled:
        st.info(
            "O altă lucrare este activă. Poți continua editarea; generarea va fi disponibilă după finalizare."
        )
        ready = False
    if st.session_state.output_format == "MP4":
        st.file_uploader(
            "Videoclip de fundal",
            type=["mp4", "m4v", "mov", "webm"],
            key="background_video",
            disabled=disabled,
            help="Maximum 100 MB, 4K și 10 minute. Sunetul fundalului este eliminat.",
            on_change=_remember_upload,
        )
        st.selectbox(
            "Poziția decupării verticale",
            list(CROP_LABELS),
            format_func=CROP_LABELS.get,
            key="crop_position",
            disabled=disabled,
        )
        st.slider(
            "Introducere cu titlu (secunde)",
            0.0,
            10.0,
            step=0.5,
            key="intro_seconds",
            disabled=disabled,
        )
        st.caption(
            "Cadru fix înaintea narațiunii; după introducere, fundalul și vocea pornesc de la început. 0 dezactivează introducerea."
        )
        st.checkbox(
            "Accept subtitrări aproximative dacă lipsesc timpii cuvintelor",
            key="allow_approximate",
            disabled=disabled,
        )
        try:
            validate_video_tools()
        except Exception as error:
            st.warning(str(error))
            ready = False
        background_ready = bool(
            st.session_state.get("background_upload")
            or st.session_state.get("background_video")
            or st.session_state.get("reuse_background_path")
        )
        if not background_ready:
            st.info("Încarcă un fundal înainte de generare.")
        ready = ready and background_ready
        if st.session_state.get("reuse_background_path"):
            st.caption("Fundalul salvat în istoric este disponibil pentru reutilizare.")
        if st.session_state.get("background_upload"):
            st.caption(f"Fundal ales: {st.session_state.background_upload.name}")
        if st.button("Previzualizează încadrarea", disabled=disabled or not ready):
            _render_preview()
    st.button(
        f"Generează {st.session_state.output_format}",
        type="primary",
        disabled=disabled or not ready,
        on_click=_start_generation,
    )
    if st.session_state.generation_error:
        st.error(st.session_state.generation_error)
    st.session_state.generator_draft = {
        key: st.session_state.get(key)
        for key in (
            "text_input",
            "title_input",
            "auto_settings_enabled",
            "language_name",
            "voice_name",
            "rate_percent",
            "pitch_hz",
            "output_format",
            "intro_seconds",
            "crop_position",
            "allow_approximate",
            "force_synthesis",
        )
    }
    st.fragment(run_every=1.0 if disabled else None)(_render_job)()
