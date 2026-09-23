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
            raise GenerationCancelled("Generarea a fost anulată.")

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
                    raise TimeoutError("Procesarea media a depășit timpul disponibil.")
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
        message = "Generarea a fost anulată. Rezultatele deja finalizate rămân în istoric."
    elif isinstance(error, (TimeoutError, subprocess.TimeoutExpired)):
        message = "Timpul de procesare a expirat. Încearcă un text sau un videoclip mai scurt."
    elif isinstance(error, ClientError):
        message = "Serviciul de voce nu este disponibil. Verifică internetul și încearcă din nou."
    elif isinstance(error, SQLAlchemyError):
        message = "Istoricul nu poate fi salvat. Verifică spațiul liber și accesul la baza de date."
    elif isinstance(error, OSError):
        message = "Fișierul nu poate fi citit sau salvat. Verifică spațiul liber și permisiunile."
    elif isinstance(error, (ValueError, RuntimeError)):
        message = str(error) or "Procesarea a eșuat. Încearcă din nou."
    else:
        message = "Procesarea a eșuat. Consultă jurnalul folosind identificatorul erorii."
    return f"{message} Cod: {error_id}"
