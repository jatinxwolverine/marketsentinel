"""Production logging infrastructure with Rich console formatting and rotating file logs."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from rich.logging import RichHandler

_LOGGERS: dict[str, logging.Logger] = {}


def setup_logger(
    name: str = "marketsentinel",
    log_level: str = "INFO",
    log_file: str | Path | None = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> logging.Logger:
    """Configures and returns a thread-safe structured logger with Rich console and file handlers.

    Args:
        name: Logger namespace name.
        log_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
        log_file: Optional file path to write log outputs.
        max_bytes: Max file size before rotating.
        backup_count: Number of rotated backup files to retain.

    Returns:
        Configured logging.Logger instance.
    """
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    # Prevent duplicate handlers if re-initialized
    if logger.handlers:
        logger.handlers.clear()

    # Rich Console Handler
    console_handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=False,
        markup=True,
    )
    console_handler.setLevel(level)
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    _LOGGERS[name] = logger
    return logger


def get_logger(name: str = "marketsentinel") -> logging.Logger:
    """Retrieves an existing logger or creates a default one if not already initialized."""
    if name in _LOGGERS:
        return _LOGGERS[name]
    return setup_logger(name=name, log_file="logs/marketsentinel.log")
