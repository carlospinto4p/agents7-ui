"""Tests for the SSE streaming chat endpoint."""

import asyncio
from types import SimpleNamespace

import pytest
from agents7.exceptions import Agents7Exception
from agents7.models.base import LLMMetrics
from fastapi import HTTPException
from routers import chat as chat_mod
from routers.chat import (
    _apply_engine_override,
    _attach_guard_collector,
    _begin_turn,
    _can_remember,
    _clean_context,
    _GuardCollector,
    _metrics_dict,
    _optional_json,
    _provider_status,
    _sse,
    _store,
    list_providers,
    open_turn,
    remember_turn,
    send_message,
    stream_message,
    stream_opening,
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
    def __init__(self, chunks, chat_response, can_open=False):
        self._chunks = chunks
        self._chat_response = chat_response
        self.can_open = can_open

    def chat(self, message):
        return SimpleNamespace(
            response="".join(self._chunks),
            metrics=self._chat_response.metrics,
        )

    async def chat_stream_async(self, message):
        return _FakeStream(self._chunks, self._chat_response)

    async def open_chat_async(self):
        return SimpleNamespace(
            response="".join(self._chunks),
            metrics=self._chat_response.metrics,
        )

    async def open_chat_stream_async(self):
        return _FakeStream(self._chunks, self._chat_response)


class _ErrChatter:
    can_open = True

    def chat(self, message):
        raise Agents7Exception("boom")

    async def chat_stream_async(self, message):
        raise Agents7Exception("boom")

    async def open_chat_async(self):
        raise Agents7Exception("boom")

    async def open_chat_stream_async(self):
        raise Agents7Exception("boom")


class _ProviderError(Exception):
    """Stand-in for a provider SDK's own error type.

    The real ones — `openai.BadRequestError`, an Anthropic auth
    error, a rate limit — are not `Agents7Exception` subclasses and
    reach the chat routes unchanged.
    """


class _ProviderErrChatter:
    """Fails every turn the way a provider SDK does, not the framework."""

    can_open = True

    def __init__(self):
        self.facts = object()
        self.fact_extractor = object()

    def chat(self, message):
        raise _ProviderError("Invalid API key sk-live-abc123")

    async def chat_stream_async(self, message):
        raise _ProviderError("Invalid API key sk-live-abc123")

    async def open_chat_async(self):
        raise _ProviderError("Invalid API key sk-live-abc123")

    async def open_chat_stream_async(self):
        raise _ProviderError("Invalid API key sk-live-abc123")

    async def remember_async(self):
        raise _ProviderError("Invalid API key sk-live-abc123")


class _FakeRequest:
    def __init__(self, body):
        self._body = body
        # start_chat reads this for per-IP start-rate limiting; None
        # is the "unknown client" case Starlette itself can produce.
        self.client = None

    async def json(self):
        return self._body


def _resp(
    tokens=5,
    prompt_tokens=3,
    duration=1.2,
    cost_cents=None,
    cached_prompt_tokens=0,
    cached=False,
    retries=0,
    retry_duration=0.0,
):
    """A chat reply, carrying the framework's real metrics model.

    Deliberately not a stand-in namespace: the payload is built by
    dumping `LLMMetrics`, so a stub that only looks like one would
    let a field added to the framework go unnoticed here — which
    is exactly how this payload fell behind twice.
    """
    return SimpleNamespace(
        metrics=LLMMetrics(
            tokens=tokens,
            prompt_tokens=prompt_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
            total_duration=duration,
            cost_cents=cost_cents,
            cached=cached,
            retries=retries,
            retry_duration=retry_duration,
        )
    )


def _guard_metrics(
    cost_cents=0.5,
    tokens=7,
    prompt_tokens=11,
    cached=False,
    retries=0,
    retry_duration=0.0,
):
    """One guard call's metrics, as `GuardEvent.metrics` carries."""
    return LLMMetrics(
        tokens=tokens,
        prompt_tokens=prompt_tokens,
        cached_prompt_tokens=0,
        total_duration=0.4,
        cost_cents=cost_cents,
        cached=cached,
        retries=retries,
        retry_duration=retry_duration,
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


# ── send_message Tests ─────────────────────────────────────────────


def test_send_unknown_session_raises_404():
    with pytest.raises(HTTPException) as ei:
        asyncio.run(send_message("nope", _FakeRequest({"message": "hi"})))
    assert ei.value.status_code == 404


def test_send_requires_message():
    sid = _store.create(_FakeChatter(["x"], _resp()))
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(send_message(sid, _FakeRequest({})))
        assert ei.value.status_code == 422
    finally:
        _store.delete(sid)


def test_send_returns_the_reply_and_metrics():
    sid = _store.create(_FakeChatter(["Ho", "la"], _resp(tokens=8)))
    try:
        result = asyncio.run(
            send_message(sid, _FakeRequest({"message": "hi"}))
        )
    finally:
        _store.delete(sid)

    assert result["response"] == "Hola"
    assert result["metrics"]["tokens"] == 8


def test_send_framework_error_raises_500_without_leaking():
    sid = _store.create(_ErrChatter())
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(send_message(sid, _FakeRequest({"message": "hi"})))
        assert ei.value.status_code == 500
        assert "boom" not in ei.value.detail
    finally:
        _store.delete(sid)


def test_send_provider_error_raises_500_without_leaking():
    """A provider SDK error is not an `Agents7Exception`.

    It used to escape the handler entirely, so the route answered 500
    with a traceback instead of the generic detail — and the API key
    in the message went out with it.
    """
    sid = _store.create(_ProviderErrChatter())
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(send_message(sid, _FakeRequest({"message": "hi"})))
        assert ei.value.status_code == 500
        assert ei.value.detail == "Internal chat error"
        assert "sk-live-abc123" not in ei.value.detail
    finally:
        _store.delete(sid)


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


def test_stream_provider_error_emits_error_event():
    """A provider SDK error must not break the stream.

    It is not an `Agents7Exception`, so it used to escape the
    generator and tear down the Server-Sent Events response instead of
    emitting the frame the frontend renders.
    """
    sid = _store.create(_ProviderErrChatter())

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
    assert "sk-live-abc123" not in text


# ── _metrics_dict Tests ────────────────────────────────────────────


def test_metrics_dict_reads_every_field():
    """The payload carries whatever the framework declares.

    Checked against the declaration rather than a hand-written
    dict, so adding a metric upstream cannot leave this payload
    quietly one field short — which is how `cached` and the
    cached token count both went missing.
    """
    payload = _metrics_dict(_resp(tokens=9, cost_cents=0.5))

    assert set(payload) == set(LLMMetrics.model_fields)
    assert payload["tokens"] == 9
    assert payload["cost_cents"] == 0.5


def test_metrics_dict_without_a_response_is_empty():
    assert _metrics_dict(None) == {}


def test_metrics_dict_carries_a_cache_hit():
    """A cached turn must be tellable from a fast free one.

    Its duration is the cache lookup and its cost is zero, so
    without the flag the line reads as a real call that happened
    to be instant — and its token counts, which are the original
    call's, read as billed a second time.
    """
    payload = _metrics_dict(_resp(cost_cents=0.0, cached=True))

    assert payload["cached"] is True


# ── open_turn Tests ────────────────────────────────────────────────


def test_open_unknown_session_raises_404():
    with pytest.raises(HTTPException) as ei:
        asyncio.run(open_turn("nope"))
    assert ei.value.status_code == 404


def test_open_rejects_an_agent_that_may_not_speak_first():
    """An agent without `can_open` must not invent an opening."""
    sid = _store.create(_FakeChatter(["hi"], _resp(), can_open=False))
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(open_turn(sid))
        assert ei.value.status_code == 422
        assert "can_open" in ei.value.detail
    finally:
        _store.delete(sid)


def test_open_returns_the_opening_text_and_metrics():
    sid = _store.create(
        _FakeChatter(["¿Qué", " tal?"], _resp(tokens=4), can_open=True)
    )
    try:
        result = asyncio.run(open_turn(sid))
    finally:
        _store.delete(sid)

    assert result["response"] == "¿Qué tal?"
    assert result["metrics"]["tokens"] == 4


def test_open_framework_error_raises_500_without_leaking():
    sid = _store.create(_ErrChatter())
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(open_turn(sid))
        assert ei.value.status_code == 500
        assert "boom" not in ei.value.detail
    finally:
        _store.delete(sid)


def test_open_provider_error_raises_500_without_leaking():
    """The opening turn is an LLM call like any other."""
    sid = _store.create(_ProviderErrChatter())
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(open_turn(sid))
        assert ei.value.status_code == 500
        assert ei.value.detail == "Internal chat error"
    finally:
        _store.delete(sid)


# ── stream_opening Tests ───────────────────────────────────────────


def test_stream_opening_unknown_session_raises_404():
    with pytest.raises(HTTPException) as ei:
        asyncio.run(stream_opening("nope"))
    assert ei.value.status_code == 404


def test_stream_opening_rejects_an_agent_that_may_not_open():
    """Rejected before the response starts, so it is a status code."""
    sid = _store.create(_FakeChatter(["hi"], _resp(), can_open=False))
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(stream_opening(sid))
        assert ei.value.status_code == 422
    finally:
        _store.delete(sid)


def test_stream_opening_emits_deltas_then_done():
    sid = _store.create(
        _FakeChatter(["Ho", "la"], _resp(tokens=6), can_open=True)
    )

    async def _run():
        response = await stream_opening(sid)
        return await _collect(response)

    try:
        frames = asyncio.run(_run())
    finally:
        _store.delete(sid)

    text = "".join(frames)
    assert 'data: {"delta": "Ho"}' in text
    assert 'data: {"delta": "la"}' in text
    assert "event: done" in text
    assert '"tokens": 6' in text


def test_stream_opening_framework_error_emits_error_event():
    sid = _store.create(_ErrChatter())

    async def _run():
        response = await stream_opening(sid)
        return await _collect(response)

    try:
        frames = asyncio.run(_run())
    finally:
        _store.delete(sid)

    text = "".join(frames)
    assert "event: error" in text
    assert "boom" not in text


def test_stream_opening_provider_error_emits_error_event():
    sid = _store.create(_ProviderErrChatter())

    async def _run():
        response = await stream_opening(sid)
        return await _collect(response)

    try:
        frames = asyncio.run(_run())
    finally:
        _store.delete(sid)

    text = "".join(frames)
    assert "event: error" in text
    assert "sk-live-abc123" not in text


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


_PRICED = {
    "provider": "openai_compat",
    "model": "deepseek-chat",
    "pricing": {"input": 0.28, "output": 0.42},
}


def test_override_keeps_pricing_for_the_same_model(monkeypatch):
    """Picking the agent's own model must not hide its cost.

    The rates were dropped on every override, so choosing the
    very model they were written for left the turn unpriced and
    the cost silently absent from the page.
    """
    captured = _capture_build_engine(monkeypatch)

    _apply_engine_override(
        _CaptureChatter(), _PRICED, "openai_compat", "deepseek-chat"
    )

    assert captured["pricing"] == {"input": 0.28, "output": 0.42}


def test_override_drops_pricing_for_a_different_model(monkeypatch):
    """Rates belong to one model, so they cannot follow another.

    Carrying them would put a confident price on a turn that was
    never billed at those rates. Unpriced is the honest answer.
    """
    captured = _capture_build_engine(monkeypatch)

    _apply_engine_override(
        _CaptureChatter(), _PRICED, "openai_compat", "deepseek-reasoner"
    )

    assert "pricing" not in captured


def test_override_drops_pricing_across_a_provider_switch(monkeypatch):
    captured = _capture_build_engine(monkeypatch)

    _apply_engine_override(
        _CaptureChatter(), _PRICED, "ollama", "deepseek-chat"
    )

    assert "pricing" not in captured


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


# ── _clean_context Tests ───────────────────────────────────────────


def test_clean_context_keeps_non_empty_values():
    assert _clean_context({"nick": "Monica28"}) == {"nick": "Monica28"}


def test_clean_context_drops_blank_values():
    """A field left empty must fall back to the declared default."""
    assert _clean_context({"nick": "  ", "other": None}) == {}


def test_clean_context_trims_and_stringifies():
    assert _clean_context({"age": 28, "nick": " Ana "}) == {
        "age": "28",
        "nick": "Ana",
    }


def test_clean_context_non_mapping_returns_empty():
    assert _clean_context(["nick"]) == {}
    assert _clean_context(None) == {}


# ── start_chat context wiring Tests ────────────────────────────────


_CTX_CONFIG = """\
name: ctx-agent
version: 1
agent_type: chatter
engine:
    provider: ollama
    model: qwen3
system_prompt: |
    Hablas con $nick.
context_params:
    nick:
        default: "ella"
        description: The other person's nickname
    hint:
        callable: html.escape
        from: nick
"""


@pytest.fixture
def ctx_catalog(tmp_path, monkeypatch):
    """A catalog holding one agent that declares a context param."""
    import routers.catalog as catalog_mod

    path = tmp_path / "examples/ctx_agent/config.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_CTX_CONFIG, encoding="utf-8")
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", tmp_path)
    return tmp_path


def _started_chatter(body, ctx_catalog):
    """Start a session with *body* and return the stored chatter."""
    from routers.chat import start_chat

    result = asyncio.run(start_chat("ctx-agent", _FakeRequest(body)))
    return _store.get(result["session_id"])


def test_start_chat_supplies_context_to_the_prompt(ctx_catalog):
    chatter = _started_chatter({"context": {"nick": "Monica28"}}, ctx_catalog)
    assert chatter.resolved_system_prompt == "Hablas con Monica28."


def test_start_chat_derives_a_value_from_the_supplied_one(ctx_catalog):
    """The form sends only `nick`; the derived value comes with it."""
    chatter = _started_chatter({"context": {"nick": "Ana&Luis"}}, ctx_catalog)
    assert chatter.resolved_context == {
        "nick": "Ana&Luis",
        "hint": "Ana&amp;Luis",
    }


def test_start_chat_without_context_uses_the_default(ctx_catalog):
    chatter = _started_chatter({}, ctx_catalog)
    assert chatter.resolved_system_prompt == "Hablas con ella."


def test_start_chat_blank_context_falls_back_to_the_default(ctx_catalog):
    chatter = _started_chatter({"context": {"nick": "   "}}, ctx_catalog)
    assert chatter.resolved_system_prompt == "Hablas con ella."


def test_start_chat_rejects_an_undeclared_context_name(ctx_catalog):
    from routers.chat import start_chat

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            start_chat(
                "ctx-agent", _FakeRequest({"context": {"nik": "Monica28"}})
            )
        )
    assert exc.value.status_code == 400


# ── start_chat can_open reporting Tests ────────────────────────────


_OPENER_CONFIG = """\
name: opener-agent
version: 1
agent_type: chatter
engine:
    provider: ollama
    model: qwen3
system_prompt: Saluda primero.
can_open: true
"""


@pytest.fixture
def opener_catalog(tmp_path, monkeypatch):
    """A catalog holding one agent that may speak first."""
    import routers.catalog as catalog_mod

    path = tmp_path / "examples/opener_agent/config.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_OPENER_CONFIG, encoding="utf-8")
    monkeypatch.setattr(catalog_mod, "CATALOG_PATH", tmp_path)
    return tmp_path


def _start(agent_name):
    """Start a session and return the response, cleaning up after."""
    from routers.chat import start_chat

    result = asyncio.run(start_chat(agent_name, _FakeRequest({})))
    _store.delete(result["session_id"])
    return result


def test_start_chat_reports_that_the_agent_may_open(opener_catalog):
    """The UI needs this to offer the opening turn at all."""
    assert _start("opener-agent")["can_open"] is True


def test_start_chat_reports_no_opening_by_default(ctx_catalog):
    assert _start("ctx-agent")["can_open"] is False


# ── remember_turn Tests ────────────────────────────────────────────


class _FactChatter:
    """A chatter that records character facts."""

    def __init__(self, facts=("Su película favorita es X",), fail=False):
        self.facts = object()  # a store; only presence matters
        self.fact_extractor = object()  # ditto
        self._facts = facts
        self._fail = fail
        self.remember_calls = 0

    async def remember_async(self):
        self.remember_calls += 1
        if self._fail:
            raise Agents7Exception("boom")
        return [SimpleNamespace(text=text) for text in self._facts]


def test_can_remember_needs_a_store_and_an_extractor():
    """Either half missing means `remember()` would raise."""
    assert _can_remember(_FactChatter()) is True
    assert _can_remember(_FakeChatter(["hi"], _resp())) is False

    half = _FactChatter()
    half.fact_extractor = None
    assert _can_remember(half) is False

    other_half = _FactChatter()
    other_half.facts = None
    assert _can_remember(other_half) is False


def test_remember_unknown_session_raises_404():
    with pytest.raises(HTTPException) as ei:
        asyncio.run(remember_turn("nope"))
    assert ei.value.status_code == 404


def test_remember_rejects_an_agent_with_no_fact_store():
    """Most agents have none; the UI must not offer them the call."""
    sid = _store.create(_FakeChatter(["hi"], _resp()))
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(remember_turn(sid))
        assert ei.value.status_code == 422
        assert "character_facts" in ei.value.detail
    finally:
        _store.delete(sid)


def test_remember_returns_the_recorded_facts():
    chatter = _FactChatter(
        facts=("Tiene un gato llamado Pixel", "No ve la tele")
    )
    sid = _store.create(chatter)
    try:
        result = asyncio.run(remember_turn(sid))
    finally:
        _store.delete(sid)

    assert result["facts"] == [
        "Tiene un gato llamado Pixel",
        "No ve la tele",
    ]
    assert chatter.remember_calls == 1


def test_remember_reports_an_empty_list_when_nothing_is_new():
    """A normal outcome, not a failure — the UI says so rather than
    showing an error."""
    sid = _store.create(_FactChatter(facts=()))
    try:
        result = asyncio.run(remember_turn(sid))
    finally:
        _store.delete(sid)
    assert result["facts"] == []


def test_remember_framework_error_raises_500_without_leaking():
    sid = _store.create(_FactChatter(fail=True))
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(remember_turn(sid))
        assert ei.value.status_code == 500
        assert "boom" not in ei.value.detail
    finally:
        _store.delete(sid)


def test_remember_provider_error_raises_500_without_leaking():
    """The fact extractor runs its own LLM call, so it fails this way
    too."""
    sid = _store.create(_ProviderErrChatter())
    try:
        with pytest.raises(HTTPException) as ei:
            asyncio.run(remember_turn(sid))
        assert ei.value.status_code == 500
        assert ei.value.detail == "Internal chat error"
    finally:
        _store.delete(sid)


def test_start_chat_reports_no_fact_store_by_default(ctx_catalog):
    """No agent in the fixture catalog declares `character_facts`."""
    assert _start("ctx-agent")["can_remember"] is False


# ── Guard cost Tests ───────────────────────────────────────────────


class _FakeGuarded:
    """A chatter with a guard, as a frozen dataclass would behave."""

    def __init__(self):
        self.guard_callback = None

    def _set_attr(self, name, value):
        object.__setattr__(self, name, value)


def test_collector_is_attached_only_to_a_guarded_chatter():
    """A plain chatter has no guard_callback and is left alone."""
    plain = SimpleNamespace()
    _attach_guard_collector(plain)

    assert not hasattr(plain, "guard_callback")


def test_collector_is_attached_to_a_guarded_chatter():
    guarded = _FakeGuarded()
    _attach_guard_collector(guarded)

    assert isinstance(guarded.guard_callback, _GuardCollector)


def test_guard_summary_says_whether_the_guard_was_cached():
    """Only when every guard call was a hit.

    One live call means the guard half of the turn was really
    made and really paid for, so the turn is not "cached".
    """
    guarded = _FakeGuarded()
    _attach_guard_collector(guarded)
    guarded.guard_callback(
        SimpleNamespace(metrics=_guard_metrics(cached=True))
    )
    guarded.guard_callback(
        SimpleNamespace(metrics=_guard_metrics(cached=False))
    )

    payload = _metrics_dict(_resp(cost_cents=1.5, cached=True), guarded)

    assert payload["cached"] is True
    assert payload["guard"]["cached"] is False
    assert payload["guard"]["cached_prompt_tokens"] == 0


def test_the_payload_reports_a_retried_reply():
    """A turn that fought the provider must not look clean.

    The seconds are not in `total_duration`, which is the
    successful attempt's own figure — so without them the page
    shows a fast turn that in fact kept the user waiting.
    """
    payload = _metrics_dict(_resp(retries=2, retry_duration=4.5))

    assert payload["retries"] == 2
    assert payload["retry_duration"] == 4.5


def test_the_guard_summary_reports_its_own_retries():
    """The guard runs its own calls, which can fail on their own.

    They are summed like every other guard figure, so a turn held
    up by the guard's retries is as visible as one held up by the
    reply's.
    """
    guarded = _FakeGuarded()
    _attach_guard_collector(guarded)
    guarded.guard_callback(
        SimpleNamespace(metrics=_guard_metrics(retries=1, retry_duration=2.0))
    )
    guarded.guard_callback(
        SimpleNamespace(metrics=_guard_metrics(retries=2, retry_duration=3.0))
    )

    payload = _metrics_dict(_resp(), guarded)

    assert payload["guard"]["retries"] == 3
    assert payload["guard"]["retry_duration"] == 5.0


def test_guard_cost_is_reported_beside_the_reply():
    """A guarded turn reports both halves and their total.

    The chatter's ChatResponse holds only the first of at least
    two LLM calls, so without the guard's own metrics the UI
    showed roughly half of what the turn really cost.
    """
    guarded = _FakeGuarded()
    _attach_guard_collector(guarded)
    guarded.guard_callback(SimpleNamespace(metrics=_guard_metrics(0.5)))

    payload = _metrics_dict(_resp(cost_cents=1.5), guarded)

    assert payload["cost_cents"] == 1.5
    assert payload["guard"]["cost_cents"] == 0.5
    assert payload["guard"]["calls"] == 1
    assert payload["total_cost_cents"] == 2.0


def test_guard_cost_sums_every_attempt():
    """A rejected reply guards more than once; all of it counts."""
    guarded = _FakeGuarded()
    _attach_guard_collector(guarded)
    for _ in range(3):
        guarded.guard_callback(SimpleNamespace(metrics=_guard_metrics(0.25)))

    payload = _metrics_dict(_resp(cost_cents=1.0), guarded)

    assert payload["guard"]["calls"] == 3
    assert payload["guard"]["cost_cents"] == pytest.approx(0.75)
    assert payload["total_cost_cents"] == pytest.approx(1.75)


def test_begin_turn_drops_the_previous_turns_guard_metrics():
    """Costs must not accumulate across turns in a session."""
    guarded = _FakeGuarded()
    _attach_guard_collector(guarded)
    guarded.guard_callback(SimpleNamespace(metrics=_guard_metrics(0.5)))

    _begin_turn(guarded)
    guarded.guard_callback(SimpleNamespace(metrics=_guard_metrics(0.25)))
    payload = _metrics_dict(_resp(cost_cents=1.0), guarded)

    assert payload["guard"]["calls"] == 1
    assert payload["guard"]["cost_cents"] == pytest.approx(0.25)


def test_unguarded_turn_reports_no_guard_key():
    """No guard is different from a guard that cost nothing."""
    payload = _metrics_dict(_resp(cost_cents=1.0), SimpleNamespace())

    assert "guard" not in payload
    assert "total_cost_cents" not in payload


def test_unpriced_guard_reports_no_total():
    """An unpriced agent must not produce a misleading total."""
    guarded = _FakeGuarded()
    _attach_guard_collector(guarded)
    guarded.guard_callback(
        SimpleNamespace(metrics=_guard_metrics(cost_cents=None))
    )

    payload = _metrics_dict(_resp(cost_cents=None), guarded)

    assert payload["guard"]["cost_cents"] is None
    assert "total_cost_cents" not in payload


def test_guard_event_without_metrics_is_ignored():
    """Using the guard's fix verbatim costs no call."""
    guarded = _FakeGuarded()
    _attach_guard_collector(guarded)
    guarded.guard_callback(SimpleNamespace(metrics=None))

    payload = _metrics_dict(_resp(cost_cents=1.0), guarded)

    assert "guard" not in payload
