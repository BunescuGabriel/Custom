import sys
from pathlib import Path

from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web import cli as streamlit_cli

from src.app import run_app
from src.db.database import init_db
from src.logging_config import configure_logging


def main() -> None:
    if get_script_run_ctx(suppress_warning=True) is None:
        configure_logging()
        init_db()
        sys.argv = ["streamlit", "run", str(Path(__file__).resolve())]
        sys.exit(streamlit_cli.main())

    run_app()


if __name__ == "__main__":
    main()
