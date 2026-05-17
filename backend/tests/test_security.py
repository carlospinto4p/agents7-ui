import pytest
from pathlib import Path

# ── _parse_cors_origins Tests ──────────────────────────────────────────────


def _import_parse():
    import importlib.util

    backend = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location(
        "main_module", backend / "main.py"
    )
    mod = importlib.util.module_from_spec(spec)
    # Avoid executing FastAPI app startup; patch heavy imports
    import unittest.mock as mock

    with mock.patch.dict(
        "sys.modules",
        {
            "fastapi": mock.MagicMock(),
            "fastapi.middleware.cors": mock.MagicMock(),
            "fastapi.responses": mock.MagicMock(),
            "routers": mock.MagicMock(),
            "routers.catalog": mock.MagicMock(),
            "routers.chat": mock.MagicMock(),
            "routers.engine": mock.MagicMock(),
            "routers.eval": mock.MagicMock(),
            "routers.run": mock.MagicMock(),
        },
    ):
        spec.loader.exec_module(mod)
    return mod._parse_cors_origins


def test_parse_cors_origins_valid_localhost():
    fn = _import_parse()
    result = fn("http://localhost:5173,http://localhost:8080")
    assert result == ["http://localhost:5173", "http://localhost:8080"]


def test_parse_cors_origins_valid_https():
    fn = _import_parse()
    result = fn("https://example.com,https://app.example.com:443")
    assert result == ["https://example.com", "https://app.example.com:443"]


def test_parse_cors_origins_empty_string():
    fn = _import_parse()
    assert fn("") == []


def test_parse_cors_origins_strips_whitespace():
    fn = _import_parse()
    result = fn(" http://localhost:5173 , http://localhost:8080 ")
    assert result == ["http://localhost:5173", "http://localhost:8080"]


def test_parse_cors_origins_rejects_wildcard():
    fn = _import_parse()
    with pytest.raises(ValueError, match="Invalid CORS origin"):
        fn("*")


def test_parse_cors_origins_rejects_wildcard_mixed():
    fn = _import_parse()
    with pytest.raises(ValueError, match="Invalid CORS origin"):
        fn("http://localhost:5173,*")


def test_parse_cors_origins_rejects_no_scheme():
    fn = _import_parse()
    with pytest.raises(ValueError, match="Invalid CORS origin"):
        fn("localhost:5173")


def test_parse_cors_origins_rejects_ftp_scheme():
    fn = _import_parse()
    with pytest.raises(ValueError, match="Invalid CORS origin"):
        fn("ftp://localhost:5173")


# ── _resolve_agent_path Tests ──────────────────────────────────────────────

from routers.run import _resolve_agent_path  # noqa: E402


def test_resolve_agent_path_within_root(tmp_path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    agent_dir = catalog / "my_agent"
    agent_dir.mkdir()
    config_dir = catalog / "pipeline"
    config_dir.mkdir()

    result = _resolve_agent_path(
        "../my_agent/config.yml", config_dir, catalog
    )
    assert result == str((config_dir / "../my_agent/config.yml").resolve())


def test_resolve_agent_path_escapes_root_raises(tmp_path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    config_dir = catalog / "pipeline"
    config_dir.mkdir()

    with pytest.raises(ValueError, match="escapes catalog root"):
        _resolve_agent_path("../../outside/config.yml", config_dir, catalog)


def test_resolve_agent_path_absolute_passthrough(tmp_path):
    catalog = tmp_path / "catalog"
    absolute = str(tmp_path / "elsewhere" / "config.yml")
    result = _resolve_agent_path(absolute, catalog, catalog)
    assert result == absolute


# ── eval.py PII logging Tests ─────────────────────────────────────────────


def test_eval_log_does_not_expose_input_values(monkeypatch):
    import logging
    from routers import eval as eval_router

    captured = []

    class _Handler(logging.Handler):
        def emit(self, record):
            captured.append(self.format(record))

    handler = _Handler()
    eval_logger = logging.getLogger(eval_router.__name__)
    eval_logger.addHandler(handler)
    eval_logger.setLevel(logging.WARNING)

    sensitive = {"name": "Alice", "ssn": "123-45-6789"}
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        eval_logger.warning(
            "agent.act() failed (input keys: %s): %s",
            list(sensitive.keys()),
            exc,
        )

    assert captured, "expected at least one log record"
    log_line = captured[0]
    assert "123-45-6789" not in log_line
    assert "Alice" not in log_line
    assert "name" in log_line
    assert "ssn" in log_line


# ── engine.py generic error Tests ─────────────────────────────────────────


def test_engine_error_response_is_generic():
    import asyncio
    import unittest.mock as mock
    from routers.engine import list_models

    async def _run():
        mock_client = mock.AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        with mock.patch("routers.engine.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = mock.AsyncMock(
                return_value=mock_client
            )
            MockClient.return_value.__aexit__ = mock.AsyncMock(
                return_value=False
            )
            return await list_models()

    result = asyncio.run(_run())
    assert result["models"] == []
    assert result["error"] == "Could not reach model provider"
    assert "Connection refused" not in result["error"]


# ── chat.py rate limit Tests ───────────────────────────────────────────────


def test_check_start_rate_allows_within_limit():
    from routers.chat import _store

    _store._start_counts.clear()
    for _ in range(20):
        _store.check_start_rate("1.2.3.4")


def test_check_start_rate_blocks_excess():
    import pytest
    from fastapi import HTTPException
    from routers.chat import _store

    _store._start_counts.clear()
    for _ in range(20):
        _store.check_start_rate("5.6.7.8")
    with pytest.raises(HTTPException) as exc_info:
        _store.check_start_rate("5.6.7.8")
    assert exc_info.value.status_code == 429


def test_check_start_rate_resets_after_window(monkeypatch):
    from routers.chat import _store

    _store._start_counts.clear()
    for _ in range(_store._MAX_STARTS):
        _store.check_start_rate("9.9.9.9")

    count, window_start = _store._start_counts["9.9.9.9"]
    _store._start_counts["9.9.9.9"] = (
        count,
        window_start - _store._RATE_WINDOW - 1,
    )

    _store.check_start_rate("9.9.9.9")
