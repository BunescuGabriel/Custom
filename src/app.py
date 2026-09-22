import streamlit as st

from src.db.database import init_db
from src.logging_config import configure_logging
from src.ui.generator_view import render_generator_view
from src.ui.history_view import render_history_view


def _render_styles() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1180px;
                padding-top: 2.5rem;
            }

            div[data-testid="stTextArea"] textarea {
                min-height: 430px;
                resize: vertical;
                line-height: 1.55;
            }

            .generation-panel {
                display: flex;
                align-items: center;
                gap: 14px;
                margin: 1rem 0;
                padding: 14px 16px;
                border: 1px solid rgba(255, 75, 75, 0.35);
                border-radius: 8px;
                background: rgba(255, 75, 75, 0.08);
            }

            .generation-spinner {
                width: 24px;
                height: 24px;
                border: 3px solid rgba(255, 255, 255, 0.2);
                border-top-color: #ff4b4b;
                border-radius: 50%;
                animation: spin 0.9s linear infinite;
                flex: 0 0 auto;
            }

            .generation-title {
                font-weight: 700;
                margin-bottom: 2px;
            }

            .generation-text {
                opacity: 0.8;
                font-size: 0.92rem;
            }

            @keyframes spin {
                to { transform: rotate(360deg); }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def run_app() -> None:
    st.set_page_config(
        page_title="Text to Audio",
        layout="wide",
    )

    configure_logging()
    init_db()
    _render_styles()

    st.title("Text to Audio")

    generator_tab, history_tab = st.tabs(["Generator", "Istoric"])
    with generator_tab:
        render_generator_view()
    with history_tab:
        render_history_view()
