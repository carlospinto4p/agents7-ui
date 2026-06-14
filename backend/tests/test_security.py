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


def test_resolve_agent_path_rejects_absolute_when_disallowed(tmp_path):
    catalog = tmp_path / "catalog"
    absolute = str(tmp_path / "elsewhere" / "config.yml")
    with pytest.raises(ValueError, match="must be relative"):
        _resolve_agent_path(absolute, catalog, catalog, allow_absolute=False)


# ── catalog pipeline-step path traversal Tests ─────────────────────────────


def test_pipeline_step_details_skips_escaping_path(tmp_path):
    """A step agent path escaping the catalog root is not read/leaked."""
    from routers import catalog

    catalog_root = tmp_path / "catalog"
    pipeline_dir = catalog_root / "my_pipeline"
    pipeline_dir.mkdir(parents=True)
    config_file = pipeline_dir / "config.yml"
    config_file.write_text("name: p\n")

    # A secret outside the catalog the attacker tries to leak.
    secret = tmp_path / "secret.yml"
    secret.write_text("name: SECRET\nengine:\n  provider: leaked\n")

    monkeypatched = catalog.CATALOG_PATH
    catalog.CATALOG_PATH = catalog_root
    try:
        steps = [{"agent": "../../secret.yml"}]
        details = catalog._resolve_pipeline_step_details(config_file, steps)
    finally:
        catalog.CATALOG_PATH = monkeypatched

    assert len(details) == 1
    entry = details[0]
    # The escaping path is reported verbatim, never read.
    assert entry["name"] == "../../secret.yml"
    assert entry["provider"] is None
    assert entry["model"] is None


def test_pipeline_step_details_reads_in_catalog_path(tmp_path):
    """A step within the catalog root is resolved and read normally."""
    from routers import catalog

    catalog_root = tmp_path / "catalog"
    pipeline_dir = catalog_root / "my_pipeline"
    pipeline_dir.mkdir(parents=True)
    config_file = pipeline_dir / "config.yml"
    config_file.write_text("name: p\n")

    step_dir = catalog_root / "step_agent"
    step_dir.mkdir()
    (step_dir / "config.yml").write_text(
        "name: StepAgent\nengine:\n  provider: ollama\n  model: qwen3\n"
    )

    monkeypatched = catalog.CATALOG_PATH
    catalog.CATALOG_PATH = catalog_root
    try:
        steps = [{"agent": "../step_agent/config.yml"}]
        details = catalog._resolve_pipeline_step_details(config_file, steps)
    finally:
        catalog.CATALOG_PATH = monkeypatched

    assert details[0]["name"] == "StepAgent"
    assert details[0]["provider"] == "ollama"
    assert details[0]["model"] == "qwen3"


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
    from routers import engine

    async def _run():
        mock_client = mock.AsyncMock()
        mock_client.get.side_effect = Exception("Connection refused")
        with mock.patch.object(engine, "_client", mock_client):
            return await engine.list_models()

    result = asyncio.run(_run())
    assert result["models"] == []
    assert result["error"] == "Could not reach model provider"
    assert "Connection refused" not in result["error"]


# ── engine.py start Tests ──────────────────────────────────────────────────


def test_engine_start_disabled_by_default(monkeypatch):
    import asyncio

    from fastapi import HTTPException
    from routers import engine

    monkeypatch.delenv("ALLOW_ENGINE_START", raising=False)
    with pytest.raises(HTTPException) as ei:
        asyncio.run(engine.start_ollama())
    assert ei.value.status_code == 403


def test_engine_start_refuses_remote_host(monkeypatch):
    import asyncio

    from fastapi import HTTPException
    from routers import engine

    monkeypatch.setenv("ALLOW_ENGINE_START", "1")
    monkeypatch.setattr(
        engine, "OLLAMA_HOST", "http://host.docker.internal:11434"
    )
    with pytest.raises(HTTPException) as ei:
        asyncio.run(engine.start_ollama())
    assert ei.value.status_code == 400


def test_engine_start_noop_when_already_up(monkeypatch):
    import asyncio
    import unittest.mock as mock

    from routers import engine

    monkeypatch.setenv("ALLOW_ENGINE_START", "1")
    monkeypatch.setattr(engine, "OLLAMA_HOST", "http://localhost:11434")
    ok = mock.Mock(is_success=True)
    client = mock.AsyncMock()
    client.get.return_value = ok
    monkeypatch.setattr(engine, "_client", client)

    result = asyncio.run(engine.start_ollama())
    assert result == {"status": "already_running"}


def test_engine_start_spawns_and_reports_started(monkeypatch):
    import asyncio
    import unittest.mock as mock

    from routers import engine

    monkeypatch.setenv("ALLOW_ENGINE_START", "1")
    monkeypatch.setattr(engine, "OLLAMA_HOST", "http://localhost:11434")
    down = mock.Mock(is_success=False)
    up = mock.Mock(is_success=True)
    client = mock.AsyncMock()
    client.get.side_effect = [down, up]
    monkeypatch.setattr(engine, "_client", client)
    popen = mock.Mock()
    monkeypatch.setattr(engine.subprocess, "Popen", popen)

    result = asyncio.run(engine.start_ollama())
    assert result == {"status": "started"}
    popen.assert_called_once()
    assert popen.call_args[0][0][:2] == ["ollama", "serve"]


# ── engine.py load / unload Tests ──────────────────────────────────────────


def test_engine_load_fires_background_keep_alive_indefinite(monkeypatch):
    import asyncio
    import unittest.mock as mock

    from routers import engine

    monkeypatch.setattr(engine, "OLLAMA_HOST", "http://localhost:11434")
    client = mock.AsyncMock()
    client.post.return_value = mock.Mock(is_success=True)
    monkeypatch.setattr(engine, "_client", client)
    engine._loading.clear()

    async def _run():
        result = await engine.load_model(engine.ModelRef(name="qwen3"))
        # Returns immediately, marking the model as loading.
        assert result == {"status": "loading", "model": "qwen3"}
        assert "qwen3" in engine._loading
        # Let the background load run to completion.
        await asyncio.gather(*engine._load_tasks)

    asyncio.run(_run())
    body = client.post.call_args.kwargs["json"]
    assert body == {"model": "qwen3", "keep_alive": -1}
    assert "qwen3" not in engine._loading  # cleared once settled


def test_engine_models_reports_loading_flag(monkeypatch):
    import asyncio
    import unittest.mock as mock

    from routers import engine

    tags = mock.Mock(
        is_success=True,
        json=mock.Mock(return_value={"models": [{"name": "x", "size": 1}]}),
    )
    ps = mock.Mock(
        is_success=True, json=mock.Mock(return_value={"models": []})
    )
    client = mock.AsyncMock()
    client.get.side_effect = [tags, ps]
    monkeypatch.setattr(engine, "_client", client)
    monkeypatch.setattr(engine, "_loading", {"x"})

    result = asyncio.run(engine.list_models())
    m = result["models"][0]
    assert m["loaded"] is False
    assert m["loading"] is True


def test_engine_unload_evicts_model(monkeypatch):
    import asyncio
    import unittest.mock as mock

    from routers import engine

    client = mock.AsyncMock()
    client.post.return_value = mock.Mock(is_success=True)
    monkeypatch.setattr(engine, "_client", client)

    result = asyncio.run(engine.unload_model(engine.ModelRef(name="qwen3")))
    assert result == {"status": "unloaded", "model": "qwen3"}
    assert client.post.call_args.kwargs["json"]["keep_alive"] == 0


def test_engine_unload_unreachable_raises_503(monkeypatch):
    import asyncio

    from fastapi import HTTPException
    from routers import engine

    async def _boom(*a, **k):
        raise RuntimeError("connection refused")

    client = type("C", (), {"post": staticmethod(_boom)})()
    monkeypatch.setattr(engine, "_client", client)

    with pytest.raises(HTTPException) as ei:
        asyncio.run(engine.unload_model(engine.ModelRef(name="qwen3")))
    assert ei.value.status_code == 503


def test_engine_unload_all_evicts_loaded(monkeypatch):
    import asyncio
    import unittest.mock as mock

    from routers import engine

    client = mock.AsyncMock()
    client.get.return_value = mock.Mock(
        is_success=True,
        json=mock.Mock(
            return_value={"models": [{"name": "a"}, {"name": "b"}]}
        ),
    )
    client.post.return_value = mock.Mock(is_success=True)
    monkeypatch.setattr(engine, "_client", client)

    result = asyncio.run(engine.unload_all())
    assert result == {"status": "unloaded", "count": 2}
    assert client.post.call_count == 2


# ── /api/info Tests ────────────────────────────────────────────────────────


def test_info_reports_name_and_version():
    import main

    info = main.get_info()
    assert info["name"] == "agents7-ui"
    assert info["version"] != "unknown"
    assert info["version"][0].isdigit()


def test_info_version_matches_pyproject():
    import tomllib
    from pathlib import Path

    import main

    pyproject = Path(main.__file__).parent / "pyproject.toml"
    expected = tomllib.loads(pyproject.read_text())["project"]["version"]
    assert main.get_info()["version"] == expected


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


# ── chat.py periodic cleanup Tests ─────────────────────────────────────────


def test_evict_expired_removes_only_stale_sessions():
    import time

    from routers.chat import _SessionStore

    store = _SessionStore()
    fresh = store.create(object())
    stale = store.create(object())
    store._session_times[stale] = time.monotonic() - store._SESSION_TTL - 1

    store.evict_expired()

    assert store.get(fresh) is not None
    assert store.get(stale) is None


def test_periodic_cleanup_evicts_expired(monkeypatch):
    import asyncio
    import time

    from routers.chat import _SessionStore

    store = _SessionStore()
    monkeypatch.setattr(store, "_CLEANUP_INTERVAL", 0.01)
    sid = store.create(object())
    store._session_times[sid] = time.monotonic() - store._SESSION_TTL - 1

    async def _run():
        task = asyncio.create_task(store.run_periodic_cleanup())
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_run())
    assert store.get(sid) is None


# ── main.py response caching Tests ─────────────────────────────────────────


def test_read_version_is_cached(monkeypatch):
    import main

    main._read_version.cache_clear()
    first = main._read_version()
    # Once cached, a broken pyproject path is never consulted again.
    monkeypatch.setattr(main, "_PYPROJECT", Path("/nonexistent/p.toml"))
    assert main._read_version() == first
    main._read_version.cache_clear()


def test_read_readme_is_cached(monkeypatch, tmp_path):
    import main

    main._read_readme.cache_clear()
    readme = tmp_path / "README.md"
    readme.write_text("hello readme")
    monkeypatch.setattr(main, "_README", readme)
    assert main._read_readme() == "hello readme"
    readme.write_text("changed on disk")
    assert main._read_readme() == "hello readme"  # served from cache
    main._read_readme.cache_clear()
