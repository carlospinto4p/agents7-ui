"""Tests for loading the repository's `.env` into the environment."""

import os
from pathlib import Path

import env_setup
import pytest


def test_env_path_points_at_ui_project_root():
    """The file read is the repository's `.env`, beside `backend/`."""
    backend = Path(env_setup.__file__).parent
    assert env_setup.ENV_PATH == backend.parent / ".env"
    assert env_setup.ENV_PATH.name == ".env"


def test_load_env_sets_unset_variable(monkeypatch, tmp_path):
    """A name absent from the environment is taken from the file."""
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert env_setup.load_env(env_file) is True
    assert os.environ["ANTHROPIC_API_KEY"] == "from-file"


def test_load_env_never_overrides_real_environment(monkeypatch, tmp_path):
    """A real environment variable wins over the file's value.

    This is what keeps `docker-compose.yml`'s `environment:` block and
    an explicit ``VAR=... uvicorn ...`` in charge.
    """
    env_file = tmp_path / ".env"
    env_file.write_text("OLLAMA_HOST=http://from-file\n", encoding="utf-8")
    monkeypatch.setenv("OLLAMA_HOST", "http://from-environment")

    env_setup.load_env(env_file)
    assert os.environ["OLLAMA_HOST"] == "http://from-environment"


def test_load_env_missing_file_is_a_no_op(tmp_path):
    """No file (the Compose container's case) raises nothing."""
    assert env_setup.load_env(tmp_path / "absent.env") is False


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
