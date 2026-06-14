"""File-based WARNING/ERROR logging for the backend.

Implements the canonical local-dev observability pattern: first-party
WARNING records are written to ``<logs>/warnings/`` and ERROR/CRITICAL
records to ``<logs>/errors/``, one file per process start, rotated by
size. A console handler keeps stdout output as before. See the global
``docker-compose-error-logging.md`` rule.

The log root is anchored to ``$LOGS_DIR/logs`` when ``LOGS_DIR`` is set
(``LOGS_DIR=/app`` in the compose stack, bind-mounted to the host), and
falls back to ``<backend>/logs`` for local runs.

Handlers are attached to the root logger so every first-party module
logger (``routers.*`` and the agents7 framework's logger) is captured
via propagation. Uvicorn configures its own loggers with
``propagate=False``, so the file handlers are also attached to
``uvicorn.error`` explicitly.
"""

import logging
import os
from datetime import datetime, timezone
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler
from pathlib import Path
from time import gmtime

_FMT = "%(asctime)s | %(levelname)s-%(name)s: %(message)s"
_DATEFMT = "%Y.%m.%d %H:%M:%S"

_configured = False


def _formatter() -> Formatter:
    """Build the shared UTC formatter."""
    f = Formatter(_FMT, datefmt=_DATEFMT)
    f.converter = gmtime  # UTC timestamps, comparable across containers
    return f


def _file_handler(path: Path, level: int) -> RotatingFileHandler:
    """Build a rotating, delayed file handler at *level*.

    :param path: Destination log file path.
    :param level: Minimum level this handler records.
    :return: A configured `RotatingFileHandler`.
    """
    handler = RotatingFileHandler(
        str(path),
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(level)
    handler.setFormatter(_formatter())
    return handler


def _logs_root() -> Path:
    """Resolve the ``logs/`` root directory.

    :return: ``$LOGS_DIR/logs`` when ``LOGS_DIR`` is set, else
        ``<backend>/logs``.
    """
    base = os.getenv("LOGS_DIR")
    if base:
        return Path(base) / "logs"
    return Path(__file__).parent / "logs"


def configure_logging() -> None:
    """Wire console + level-segregated file logging (idempotent).

    WARNING records go to ``warnings/<stamp>.log`` (WARNING only, never
    ERROR — a level filter enforces the clean split) and ERROR/CRITICAL
    records to ``errors/<stamp>.log``. Safe to call more than once; only
    the first call installs handlers.
    """
    global _configured
    if _configured:
        return
    _configured = True

    root = _logs_root()
    warnings_dir = root / "warnings"
    errors_dir = root / "errors"
    warnings_dir.mkdir(parents=True, exist_ok=True)
    errors_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    warning_handler = _file_handler(
        warnings_dir / f"{stamp}.log", logging.WARNING
    )
    # Clean split: WARNING-only, never ERROR.
    warning_handler.addFilter(lambda r: r.levelno == logging.WARNING)
    error_handler = _file_handler(errors_dir / f"{stamp}.log", logging.ERROR)

    console = StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(_formatter())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console)
    root_logger.addHandler(warning_handler)
    root_logger.addHandler(error_handler)

    # Uvicorn's loggers do not propagate to root; capture their
    # warnings/errors in the same files. Its dictConfig has already run
    # by the time the app module is imported.
    for name in ("uvicorn", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.addHandler(warning_handler)
        uv_logger.addHandler(error_handler)
