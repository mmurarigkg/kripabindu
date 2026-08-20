"""Журналирование. Все исключения проекта проходят через этот модуль."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

_LOGGER_NAME = "krishna_quotes"
_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(log_file: Path, *, verbose: bool = False) -> logging.Logger:
    """Настроить журнал приложения и перехват необработанных исключений."""
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(_FORMAT)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if verbose:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    sys.excepthook = _make_excepthook(logger)
    return logger


def get_logger(module: str | None = None) -> logging.Logger:
    """Получить журнал модуля."""
    if module:
        return logging.getLogger(f"{_LOGGER_NAME}.{module}")
    return logging.getLogger(_LOGGER_NAME)


def _make_excepthook(logger: logging.Logger):
    def hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            return
        logger.critical(
            "Необработанное исключение", exc_info=(exc_type, exc_value, exc_tb)
        )

    return hook
