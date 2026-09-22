import json
import logging
import os
import sys
import time
from logging.handlers import RotatingFileHandler
from threading import Lock
from typing import ClassVar

from src.config import LOG_DIR

_configuration_lock = Lock()


class JsonFormatter(logging.Formatter):
    converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


class ConsoleFormatter(logging.Formatter):
    converter = time.gmtime
    COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "\033[34m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[35m",
    }

    def __init__(self, *, use_colors: bool) -> None:
        super().__init__(
            "[{asctime}.{msecs:03.0f}][{levelname}][{module}] {message}",
            "%Y-%m-%d,%H:%M:%S",
            style="{",
        )
        self.use_colors = use_colors

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self.COLORS.get(record.levelno)
        if self.use_colors and color:
            return f"{color}{message}\033[0m"
        return message


def configure_logging() -> None:
    with _configuration_lock:
        logger = logging.getLogger("src")
        if logger.handlers:
            return

        logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())
        logger.propagate = False
        logger.disabled = False

        console_handler = logging.StreamHandler(sys.stdout)
        if os.environ.get("LOG_FORMAT", "").lower() == "json":
            console_handler.setFormatter(JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%SZ"))
        else:
            console_handler.setFormatter(
                ConsoleFormatter(use_colors=sys.stdout.isatty() and "NO_COLOR" not in os.environ)
            )
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                LOG_DIR / "app.log",
                maxBytes=10 * 1024 * 1024,
                backupCount=100,
                encoding="utf-8",
            )
            file_handler.setFormatter(ConsoleFormatter(use_colors=False))
            logger.addHandler(file_handler)

        logger.addHandler(console_handler)
