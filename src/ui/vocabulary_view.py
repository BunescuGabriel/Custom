import html
import json
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

from src.config import VOICE_OPTIONS
from src.db.models import GenerationJob
from src.db.repositories import get_record
from src.services.bilingual_vocabulary_service import parse_vocabulary_pairs
from src.services.job_service import ACTIVE_STATUSES, cancel_job, submit_job
from src.services.operations import describe_error
from src.ui.common import as_utc
from src.ui.labels import STATUS_LABELS


def _init_state() -> None:
    defaults = {
        "vocabulary_text": "",
        "vocabulary_title": "Vocabular engleză-română",
        "vocabulary_english_voice": "Jenny",
        "vocabulary_romanian_voice": "Alina",
        "vocabulary_rate": 0,
        "vocabulary_english_pause": 600,
        "vocabulary_pair_pause": 1000,
        "vocabulary_job_id": None,
        "vocabulary_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _start_generation() -> None:
    try:
        job_id = submit_job(
            {
                "kind": "bilingual_vocabulary",
                "vocabulary": {
                    "text": st.session_state.vocabulary_text,
                    "title": st.session_state.vocabulary_title,
                    "english_voice": VOICE_OPTIONS["Engleza"][
                        st.session_state.vocabulary_english_voice
                    ],
                    "romanian_voice": VOICE_OPTIONS["Romana"][
                        st.session_state.vocabulary_romanian_voice
                    ],
                    "rate_percent": st.session_state.vocabulary_rate,
                    "english_pause_ms": st.session_state.vocabulary_english_pause,
                    "pair_pause_ms": st.session_state.vocabulary_pair_pause,
                },
            }
        )
        st.session_state.vocabulary_job_id = job_id
        st.session_state.vocabulary_error = None
    except Exception as error:
        st.session_state.vocabulary_error = describe_error(error)


def _render_job() -> None:
    job_id = st.session_state.get("vocabulary_job_id")
    if not job_id:
        return
    job = get_record(GenerationJob, job_id)
    if job is None:
        st.warning("Lucrarea nu mai există.")
        return
    active = job.status in ACTIVE_STATUSES
    elapsed = (
        (datetime.now(UTC) if active else as_utc(job.updated_at)) - as_utc(job.created_at)
    ).total_seconds()
    st.markdown(
        f'<div class="generation-panel" role="status" aria-live="polite">'
        f"<strong>{html.escape(job.stage)}</strong> · {elapsed:.0f} secunde</div>",
        unsafe_allow_html=True,
    )
    st.caption(f"Lucrare: {job.id} · {STATUS_LABELS.get(job.status, job.status)}")
    if active:
        st.button(
            "Anulează generarea",
            key=f"cancel_vocabulary_{job.id}",
            on_click=cancel_job,
            args=(job.id,),
            disabled=job.cancel_requested,
        )
    if job.error_message:
        st.error(job.error_message)
    parameters = json.loads(job.parameters)
    result = parameters.get("result")
    if job.status == "completed" and result:
        path = Path(result["file_path"])
        if path.is_file():
            data = path.read_bytes()
            st.audio(data, format="audio/mpeg")
            st.download_button(
                "Descarcă MP3",
                data=data,
                file_name=result["file_name"],
                mime="audio/mpeg",
                key=f"download_vocabulary_{job.id}",
            )
        else:
            st.warning("Fișierul audio nu mai este disponibil.")


def render_vocabulary_view() -> None:
    _init_state()
    job = (
        get_record(GenerationJob, st.session_state.vocabulary_job_id)
        if st.session_state.vocabulary_job_id
        else None
    )
    disabled = bool(job and job.status in ACTIVE_STATUSES)
    st.caption("O voce engleză citește termenul, apoi o voce română citește traducerea.")
    st.code("Improve | A îmbunătăți\nChoose | A alege", language=None)
    st.text_area("Vocabular", key="vocabulary_text", height=300, max_chars=12000, disabled=disabled)
    try:
        pair_count = len(parse_vocabulary_pairs(st.session_state.vocabulary_text))
        st.caption(f"{pair_count} perechi detectate.")
    except ValueError as error:
        if st.session_state.vocabulary_text.strip():
            st.warning(str(error))
    st.text_input("Titlu", key="vocabulary_title", max_chars=140, disabled=disabled)
    left, right = st.columns(2)
    with left:
        st.selectbox(
            "Voce engleză",
            list(VOICE_OPTIONS["Engleza"]),
            key="vocabulary_english_voice",
            disabled=disabled,
        )
        st.slider(
            "Pauză după engleză",
            0,
            3000,
            step=100,
            format="%d ms",
            key="vocabulary_english_pause",
            disabled=disabled,
        )
    with right:
        st.selectbox(
            "Voce română",
            list(VOICE_OPTIONS["Romana"]),
            key="vocabulary_romanian_voice",
            disabled=disabled,
        )
        st.slider(
            "Pauză între perechi",
            0,
            5000,
            step=100,
            format="%d ms",
            key="vocabulary_pair_pause",
            disabled=disabled,
        )
    st.slider("Viteză", -40, 40, step=1, format="%d%%", key="vocabulary_rate", disabled=disabled)
    st.button(
        "Generează MP3 bilingv",
        type="primary",
        disabled=disabled or not st.session_state.vocabulary_text.strip(),
        on_click=_start_generation,
    )
    if st.session_state.vocabulary_error:
        st.error(st.session_state.vocabulary_error)
    st.fragment(run_every=1.0 if disabled else None)(_render_job)()
