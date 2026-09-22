import sys
from pathlib import Path

from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.web import cli as streamlit_cli

from src.app import run_app


def main() -> None:
    if get_script_run_ctx() is None:
        sys.argv = ["streamlit", "run", str(Path(__file__).resolve())]
        sys.exit(streamlit_cli.main())

    run_app()


if __name__ == "__main__":
    main()
