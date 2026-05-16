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
