"""Tests for the SSE streaming chat endpoint."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from agents7.exceptions import Agents7Exception
from routers.chat import _sse, _store, stream_message


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
