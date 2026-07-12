"""Tests for the SSE streaming chat endpoint."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from agents7.exceptions import Agents7Exception
from routers import chat as chat_mod
from routers.chat import (
    _apply_engine_override,
    _optional_json,
    _provider_status,
    _sse,
    _store,
    list_providers,
    stream_message,
)


# ── Fakes ──────────────────────────────────────────────────────────


class _FakeStream:
    """Async-iterable stand-in for a ChatterAsyncStreamResult."""

    def __init__(self, chunks, chat_response):
        self._chunks = chunks
        self.chat_response = chat_response

    async def __aiter__(self):
        for chunk in self._chunks:
            yield chunk


class _FakeChatter:
    def __init__(self, chunks, chat_response):
        self._chunks = chunks
        self._chat_response = chat_response

    async def chat_stream_async(self, message):
        return _FakeStream(self._chunks, self._chat_response)


class _ErrChatter:
    async def chat_stream_async(self, message):
        raise Agents7Exception("boom")


class _FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def _resp(tokens=5, prompt_tokens=3, duration=1.2, cost_cents=None):
    return SimpleNamespace(
        metrics=SimpleNamespace(
            tokens=tokens,
            prompt_tokens=prompt_tokens,
            total_duration=duration,
            cost_cents=cost_cents,
        )
    )


async def _collect(response):
    return [frame async for frame in response.body_iterator]


# ── _sse Tests ─────────────────────────────────────────────────────


def test_sse_plain_frame():
    frame = _sse({"delta": "hi"})
    assert frame == 'data: {"delta": "hi"}\n\n'


def test_sse_named_event():
    frame = _sse({"metrics": {}}, event="done")
    assert frame == 'event: done\ndata: {"metrics": {}}\n\n'


def test_sse_preserves_unicode():
    frame = _sse({"delta": "héllo"})
    assert "héllo" in frame


# ── stream_message Tests ───────────────────────────────────────────


def test_stream_unknown_session_raises_404():
    with pytest.raises(HTTPException) as ei:
        asyncio.run(stream_message("nope", _FakeRequest({"message": "hi"})))
    assert ei.value.status_code == 404


def test_stream_requires_message():
    sid = _store.create(_FakeChatter(["x"], _resp()))
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(stream_message(sid, _FakeRequest({})))
        assert ei.value.status_code == 422
    finally:
        _store.delete(sid)


def test_stream_emits_deltas_then_done():
    sid = _store.create(
        _FakeChatter(
            ["He", "llo"], _resp(tokens=7, duration=0.5, cost_cents=0.12)
        )
    )

    async def _run():
        response = await stream_message(sid, _FakeRequest({"message": "hi"}))
        return await _collect(response)

    try:
        frames = asyncio.run(_run())
    finally:
        _store.delete(sid)

    text = "".join(frames)
    assert 'data: {"delta": "He"}' in text
    assert 'data: {"delta": "llo"}' in text
    assert "event: done" in text
    assert '"tokens": 7' in text
    assert '"total_duration": 0.5' in text
    assert '"cost_cents": 0.12' in text


def test_stream_done_with_no_chat_response_sends_empty_metrics():
    sid = _store.create(_FakeChatter(["x"], None))

    async def _run():
        response = await stream_message(sid, _FakeRequest({"message": "hi"}))
        return await _collect(response)

    try:
        frames = asyncio.run(_run())
    finally:
        _store.delete(sid)

    text = "".join(frames)
    assert "event: done" in text
    assert '"metrics": {}' in text


def test_stream_framework_error_emits_error_event():
    sid = _store.create(_ErrChatter())

    async def _run():
        response = await stream_message(sid, _FakeRequest({"message": "hi"}))
        return await _collect(response)

    try:
        frames = asyncio.run(_run())
    finally:
        _store.delete(sid)

    text = "".join(frames)
    assert "event: error" in text
    assert "Internal chat error" in text
    # The raw exception text never leaks to the client.
    assert "boom" not in text


# ── _optional_json Tests ───────────────────────────────────────────


class _NoBodyRequest:
    async def json(self):
        raise ValueError("no body")


class _JsonRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def test_optional_json_missing_body_returns_empty():
    assert asyncio.run(_optional_json(_NoBodyRequest())) == {}


def test_optional_json_returns_dict_body():
    body = {"provider": "ollama", "model": "x"}
    assert asyncio.run(_optional_json(_JsonRequest(body))) == body


def test_optional_json_non_dict_returns_empty():
    assert asyncio.run(_optional_json(_JsonRequest([1, 2]))) == {}


# ── _apply_engine_override Tests ───────────────────────────────────


class _CaptureChatter:
    """Chatter stand-in that records the engine set on it."""

    def __init__(self):
        self.engine = None

    def _set_attr(self, name, value):
        setattr(self, name, value)


def _capture_build_engine(monkeypatch):
    """Patch `build_engine` to record its config and return a stub."""
    captured = {}

    def fake_build(cfg):
        captured.clear()
        captured.update(cfg)
        return SimpleNamespace(
            provider=cfg["provider"], model_name=cfg["model"]
        )

    monkeypatch.setattr(chat_mod, "build_engine", fake_build)
    return captured


def test_override_switch_provider_drops_connection_keys(monkeypatch):
    captured = _capture_build_engine(monkeypatch)
    chatter = _CaptureChatter()
    orig = {
        "provider": "ollama",
        "model": "qwen2.5:3b",
        "base_url": "http://x",
        "api_key": "secret",
        "retry": {"max_retries": 2},
    }
    _apply_engine_override(chatter, orig, "anthropic", "claude-x")

    assert captured["provider"] == "anthropic"
    assert captured["model"] == "claude-x"
    # Connection settings must not cross a provider switch.
    assert "base_url" not in captured
    assert "api_key" not in captured
    # Provider-agnostic settings carry over.
    assert captured["retry"] == {"max_retries": 2}
    assert chatter.engine.model_name == "claude-x"


def test_override_same_provider_keeps_connection_keys(monkeypatch):
    captured = _capture_build_engine(monkeypatch)
    chatter = _CaptureChatter()
    orig = {
        "provider": "openai_compat",
        "model": "gpt-a",
        "base_url": "http://x",
        "api_key": "secret",
    }
    _apply_engine_override(chatter, orig, "openai_compat", "gpt-b")

    assert captured["base_url"] == "http://x"
    assert captured["api_key"] == "secret"
    assert captured["model"] == "gpt-b"


def test_override_empty_model_becomes_none(monkeypatch):
    captured = _capture_build_engine(monkeypatch)
    _apply_engine_override(
        _CaptureChatter(), {"provider": "openai_compat"}, "openai_compat", ""
    )
    assert captured["model"] is None


# ── provider status Tests ──────────────────────────────────────────


def test_provider_status_ollama_always_ready():
    status = _provider_status("ollama")
    assert status["ready"] is True
    assert status["detail"] == ""


def test_provider_status_anthropic_ready_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    status = _provider_status("anthropic")
    assert status["ready"] is True
    assert status["detail"] == ""


def test_provider_status_anthropic_not_ready_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    status = _provider_status("anthropic")
    assert status["ready"] is False
    assert "ANTHROPIC_API_KEY" in status["detail"]


def test_provider_status_openai_compat_reports_env_model(monkeypatch):
    monkeypatch.setenv("OPENAI_COMPAT_MODEL_NAME", "deepseek-chat")
    status = _provider_status("openai_compat")
    assert status["model"] == "deepseek-chat"


def test_list_providers_lists_all_in_order():
    names = [p["name"] for p in list_providers()["providers"]]
    assert names == ["ollama", "anthropic", "openai_compat"]
