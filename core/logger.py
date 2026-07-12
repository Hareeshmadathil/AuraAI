"""
Central logging system for AuraAI Creator OS.

All AuraAI modules should request loggers through ``get_logger``.
This keeps terminal output, rotating log files, future dashboard logs,
and error tracking consistent across the entire application.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock

from config.settings import (
    APPLICATION_LOG_FILE,
    ERROR_LOG_FILE,
    LOG_LEVEL,
    LOG_TO_CONSOLE,
    LOG_TO_FILE,
)
from core.constants import DEFAULT_LOGGER_NAME


LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(lineno)d | %(message)s"
)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_LOG_FILE_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 5

_logging_lock = Lock()
_logging_configured = False


class MaximumLevelFilter(logging.Filter):
    """
    Allow only log records at or below a configured severity.

    This is useful for keeping normal activity out of the dedicated
    error log while still allowing full logs in the main application log.
    """

    def __init__(self, maximum_level: int) -> None:
        super().__init__()
        self.maximum_level = maximum_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.maximum_level


def _resolve_log_level(level_name: str) -> int:
    """
    Convert a configured log-level name into a logging constant.

    Invalid values fall back safely to ``logging.INFO``.
    """

    resolved_level = getattr(logging, level_name.upper(), logging.INFO)

    if not isinstance(resolved_level, int):
        return logging.INFO

    return resolved_level


def _build_formatter() -> logging.Formatter:
    """Create AuraAI's standard log formatter."""

    return logging.Formatter(
        fmt=LOG_FORMAT,
        datefmt=DATE_FORMAT,
    )


def _build_console_handler(log_level: int) -> logging.Handler:
    """Create a console handler for developer-visible logs."""

    handler = logging.StreamHandler()
    handler.setLevel(log_level)
    handler.setFormatter(_build_formatter())

    return handler


def _build_rotating_file_handler(
    file_path: Path,
    *,
    level: int,
) -> RotatingFileHandler:
    """
    Create a rotating UTF-8 file handler.

    Args:
        file_path:
            Destination log file.
        level:
            Minimum severity accepted by this handler.
    """

    file_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        filename=file_path,
        maxBytes=MAX_LOG_FILE_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(_build_formatter())

    return handler


def configure_logging(*, force: bool = False) -> None:
    """
    Configure AuraAI's root application logger.

    This function is safe to call repeatedly. Logging is configured only
    once unless ``force=True`` is supplied.

    Args:
        force:
            Remove and rebuild existing AuraAI handlers.
    """

    global _logging_configured

    with _logging_lock:
        if _logging_configured and not force:
            return

        log_level = _resolve_log_level(LOG_LEVEL)

        root_logger = logging.getLogger(DEFAULT_LOGGER_NAME)
        root_logger.setLevel(log_level)
        root_logger.propagate = False

        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            handler.close()

        if LOG_TO_CONSOLE:
            root_logger.addHandler(
                _build_console_handler(log_level)
            )

        if LOG_TO_FILE:
            application_handler = _build_rotating_file_handler(
                APPLICATION_LOG_FILE,
                level=log_level,
            )
            root_logger.addHandler(application_handler)

            error_handler = _build_rotating_file_handler(
                ERROR_LOG_FILE,
                level=logging.ERROR,
            )
            root_logger.addHandler(error_handler)

        if not root_logger.handlers:
            root_logger.addHandler(logging.NullHandler())

        _logging_configured = True


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Return a configured AuraAI logger.

    Modules should normally call:

    ``logger = get_logger(__name__)``

    Args:
        name:
            Usually the caller's ``__name__`` value.

    Returns:
        A configured child logger under the ``auraai`` namespace.
    """

    configure_logging()

    if not name:
        return logging.getLogger(DEFAULT_LOGGER_NAME)

    if name == DEFAULT_LOGGER_NAME:
        return logging.getLogger(DEFAULT_LOGGER_NAME)

    clean_name = name.removeprefix(f"{DEFAULT_LOGGER_NAME}.")

    return logging.getLogger(
        f"{DEFAULT_LOGGER_NAME}.{clean_name}"
    )


def log_exception(
    logger: logging.Logger,
    message: str,
    *,
    exc_info: BaseException | bool | None = True,
) -> None:
    """
    Record an exception with traceback information.

    Args:
        logger:
            Logger returned by ``get_logger``.
        message:
            Human-readable context for the failure.
        exc_info:
            Exception information passed to ``logger.error``.
    """

    logger.error(
        message,
        exc_info=exc_info,
    )