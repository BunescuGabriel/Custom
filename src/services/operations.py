import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from aiohttp import ClientError
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class GenerationCancelled(RuntimeError):
    pass


@dataclass
class OperationControl:
    progress: Callable[[str], None] = lambda _stage: None
    cancelled: Callable[[], bool] = lambda: False
    record: Callable[[str, int], None] = lambda _kind, _record_id: None

    def check(self) -> None:
        if self.cancelled():
            raise GenerationCancelled("Generation was cancelled.")

    def report(self, stage: str) -> None:
        self.check()
        self.progress(stage)


def run_process(
    command: list[str], timeout: float, control: OperationControl | None = None, cwd=None
):
    control = control or OperationControl()
    control.check()
    started = monotonic()
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        cwd=cwd,
    ) as process:
        try:
            while True:
                control.check()
                remaining = timeout - (monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError("Media processing exceeded the available time.")
                try:
                    stdout, stderr = process.communicate(timeout=min(0.25, remaining))
                    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()


def describe_error(error: Exception) -> str:
    error_id = uuid4().hex[:10]
    logger.error(
        "operation_failed error_id=%s", error_id, exc_info=(type(error), error, error.__traceback__)
    )
    if isinstance(error, GenerationCancelled):
        message = "Generation was cancelled. Completed results remain in history."
    elif isinstance(error, (TimeoutError, subprocess.TimeoutExpired)):
        message = "Processing timed out. Try shorter text or a shorter video."
    elif isinstance(error, ClientError):
        message = "The voice service is unavailable. Check your internet connection and try again."
    elif isinstance(error, SQLAlchemyError):
        message = "History could not be saved. Check free space and database access."
    elif isinstance(error, OSError):
        message = "The file could not be read or saved. Check free space and permissions."
    elif isinstance(error, (ValueError, RuntimeError)):
        message = str(error) or "Processing failed. Try again."
    else:
        message = "Processing failed. Check the log using the error identifier."
    return f"{message} Cod: {error_id}"
