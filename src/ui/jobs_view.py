import json

import streamlit as st

from src.db.repositories import list_jobs
from src.services.job_service import ACTIVE_STATUSES, cancel_job
from src.services.media_service import cleanup_orphans, delete_job, storage_bytes
from src.services.operations import describe_error
from src.ui.common import as_utc, format_size
from src.ui.labels import STATUS_LABELS


def _open_job(job_id: str) -> None:
    st.session_state["active_job_id"] = job_id
    st.query_params["job"] = job_id
    st.session_state["navigation"] = "Generator"


def render_jobs_view() -> None:
    st.subheader("Lucrări și stocare")
    st.button("Actualizează")
    for job in list_jobs():
        parameters = json.loads(job.parameters)
        with st.expander(
            f"{parameters['audio']['title']} · {STATUS_LABELS.get(job.status, job.status)} · {job.id[:8]}"
        ):
            st.caption(f"{as_utc(job.created_at):%Y-%m-%d %H:%M:%S} UTC · {job.stage}")
            st.button(
                "Deschide rezultatul", key=f"open_{job.id}", on_click=_open_job, args=(job.id,)
            )
            if job.status in ACTIVE_STATUSES:
                st.button(
                    "Anulează",
                    key=f"stop_{job.id}",
                    on_click=cancel_job,
                    args=(job.id,),
                    disabled=job.cancel_requested,
                )
            else:
                if st.button("Reia / editează lucrarea", key=f"retry_{job.id}"):
                    st.session_state["restore_request"] = {
                        **parameters,
                        "audio_generation_id": job.audio_generation_id,
                        "output_format": parameters.get("output_format", "MP3"),
                    }
                    st.session_state["pending_navigation"] = "Generator"
                    st.rerun()
            if job.error_message:
                st.error(job.error_message)
            confirmed = st.checkbox(
                "Șterge parametrii acestei lucrări",
                key=f"confirm_job_{job.id}",
                disabled=job.status in ACTIVE_STATUSES,
            )
            if st.button(
                "Șterge lucrarea",
                key=f"delete_job_{job.id}",
                disabled=not confirmed or st.session_state.get("generation_busy", False),
            ):
                try:
                    delete_job(job.id)
                    st.rerun()
                except Exception as error:
                    st.error(describe_error(error))
    st.caption(
        f"Spațiu media ocupat: {format_size(storage_bytes())}. Istoricul și fișierele sunt păstrate până la ștergere."
    )
    st.caption(
        "Curățarea elimină numai fișiere fără referințe, mai vechi de 24 de ore. Resursele partajate rămân disponibile."
    )
    if st.button(
        "Curăță fișierele orfane", disabled=st.session_state.get("generation_busy", False)
    ):
        try:
            count, freed = cleanup_orphans()
            st.success(f"Șterse {count} fișiere; eliberat {format_size(freed)}.")
        except Exception as error:
            st.error(describe_error(error))
