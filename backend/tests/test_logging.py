"""Tests for the file-based WARNING/ERROR logging setup."""

import logging
from pathlib import Path

import logging_setup
import pytest


def _only_log_text(directory: Path) -> str:
    """Return the concatenated text of every ``*.log`` in *directory*."""
    return "".join(
        p.read_text(encoding="utf-8") for p in directory.glob("*.log")
    )


def test_logs_root_honors_env(monkeypatch, tmp_path):
    """`LOGS_DIR` anchors the log root; unset falls back to backend."""
    monkeypatch.setenv("LOGS_DIR", str(tmp_path))
    assert logging_setup._logs_root() == tmp_path / "logs"

    monkeypatch.delenv("LOGS_DIR", raising=False)
    assert logging_setup._logs_root().name == "logs"


def test_configure_logging_clean_level_split(monkeypatch, tmp_path):
    """WARNING -> warnings/, ERROR -> errors/, with no cross-leak."""
    monkeypatch.setenv("LOGS_DIR", str(tmp_path))
    monkeypatch.setattr(logging_setup, "_configured", False)

    names = ("", "uvicorn", "uvicorn.error")
    saved = {n: logging.getLogger(n).handlers[:] for n in names}
    saved_level = logging.getLogger().level
    try:
        logging_setup.configure_logging()

        log = logging.getLogger("routers.test_split")
        log.warning("a warning line")
        log.error("an error line")
        for handler in logging.getLogger().handlers:
            handler.flush()

        warning_text = _only_log_text(tmp_path / "logs" / "warnings")
        error_text = _only_log_text(tmp_path / "logs" / "errors")

        assert "a warning line" in warning_text
        assert "an error line" not in warning_text
        assert "an error line" in error_text
        assert "a warning line" not in error_text
    finally:
        for name, handlers in saved.items():
            current = logging.getLogger(name)
            for handler in current.handlers:
                if handler not in handlers:
                    handler.close()
            current.handlers[:] = handlers
        logging.getLogger().setLevel(saved_level)


def test_configure_logging_idempotent(monkeypatch, tmp_path):
    """A second call installs no extra root handlers."""
    monkeypatch.setenv("LOGS_DIR", str(tmp_path))
    monkeypatch.setattr(logging_setup, "_configured", False)

    root = logging.getLogger()
    saved = root.handlers[:]
    saved_level = root.level
    try:
        logging_setup.configure_logging()
        count_after_first = len(root.handlers)
        logging_setup.configure_logging()
        assert len(root.handlers) == count_after_first
    finally:
        for handler in root.handlers:
            if handler not in saved:
                handler.close()
        root.handlers[:] = saved
        root.setLevel(saved_level)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
