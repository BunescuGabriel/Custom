import streamlit as st

from src.db.database import init_db
from src.logging_config import configure_logging
from src.ui.generator_view import render_generator_view
from src.ui.history_view import render_history_view
from src.ui.video_history_view import render_video_history_view


def _render_styles() -> None:
    st.markdown(
        """
        <style>
            .block-container {
                width: min(100% - 2rem, 1280px);
                max-width: 1280px;
                padding: clamp(1rem, 3vw, 2.5rem) 0 2rem;
            }

            div[data-testid="stTextArea"] textarea {
                height: clamp(260px, 46vh, 430px);
                min-height: 260px;
                resize: vertical;
                line-height: 1.55;
            }

            h1 {
                font-size: clamp(2.1rem, 4vw, 3.4rem) !important;
                line-height: 1.08 !important;
            }

            div[data-testid="stTabs"] button {
                min-height: 42px;
            }

            div[data-testid="stExpander"] summary {
                overflow-wrap: anywhere;
            }

            div[data-testid="stAudio"] {
                width: 100%;
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

            @media (max-width: 900px) {
                .block-container {
                    width: min(100% - 1rem, 760px);
                    padding-top: 1rem;
                }

                div[data-testid="stTextArea"] textarea {
                    height: clamp(240px, 42vh, 340px);
                    min-height: 220px;
                }

                div[data-testid="stHorizontalBlock"] {
                    flex-wrap: wrap;
                    gap: 0.75rem;
                }

                div[data-testid="stHorizontalBlock"] > div {
                    min-width: 100% !important;
                    flex: 1 1 100% !important;
                }

                div[data-testid="stButton"] button,
                div[data-testid="stDownloadButton"] button {
                    width: 100%;
                }

                .generation-panel {
                    align-items: flex-start;
                }
            }

            @media (max-width: 480px) {
                .block-container {
                    width: calc(100% - 0.75rem);
                    padding-bottom: 1rem;
                }

                div[data-testid="stTextArea"] textarea {
                    height: 260px;
                }

                .generation-panel {
                    padding: 12px;
                }
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

    generator_tab, history_tab, video_history_tab = st.tabs(
        ["Generator", "Istoric audio", "Istoric video"]
    )
    with generator_tab:
        render_generator_view()
    with history_tab:
        render_history_view()
    with video_history_tab:
        render_video_history_view()
