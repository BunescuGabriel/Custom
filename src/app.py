import streamlit as st

from src.db.database import init_db
from src.db.repositories import has_active_jobs
from src.logging_config import configure_logging
from src.services.job_service import recover_interrupted_jobs
from src.ui.generator_view import render_generator_view
from src.ui.history_view import render_history_view
from src.ui.jobs_view import render_jobs_view
from src.ui.labels import PAGES
from src.ui.video_history_view import render_video_history_view


def _render_styles() -> None:
    st.markdown(
        """
        <style>
            .block-container { max-width: 1100px; padding-top: 2rem; }
            .generation-panel {
                padding: 1rem; border: 1px solid #999; border-radius: 8px;
                margin: 1rem 0; overflow-wrap: anywhere;
            }
            @media (prefers-reduced-motion: reduce) {
                .generation-panel { animation: none; transition: none; }
            }
            @media (max-width: 480px) {
                .block-container { padding-left: 1rem; padding-right: 1rem; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def run_app() -> None:
    st.set_page_config(page_title="Text în audio și video", layout="wide")
    configure_logging()
    try:
        init_db()
        recover_interrupted_jobs()
        st.session_state.generation_busy = has_active_jobs()
    except Exception:
        st.error(
            "Stocarea nu poate fi inițializată. Verifică spațiul liber și jurnalul aplicației."
        )
        st.stop()
    _render_styles()
    st.title("Text în audio și video")
    if pending := st.session_state.pop("pending_navigation", None):
        st.session_state["navigation"] = pending
    page = st.radio("Navigare", PAGES, key="navigation", horizontal=True)
    views = dict(
        zip(
            PAGES,
            (
                render_generator_view,
                render_history_view,
                render_video_history_view,
                render_jobs_view,
            ),
            strict=True,
        )
    )
    views[page]()
