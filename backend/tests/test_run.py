"""Tests for the single-run endpoint's input routing.

The framework's single ``act()`` only accepts a dict, while a bare
scalar (a single free-text string, as several catalog agents use) must
go through ``act_in_batch`` — the same path eval uses. These tests lock
that routing in.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import routers.run as run_mod
from routers.run import run_agent


# ── Fakes ──────────────────────────────────────────────────────────


class _FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


def _agent_response(output):
    """Build an AgentResponse-shaped stand-in."""
    model = (
        None if output is None else SimpleNamespace(model_dump=lambda: output)
    )
    return SimpleNamespace(
        model=model,
        response="raw text",
        metrics=SimpleNamespace(
            tokens=7,
            prompt_tokens=3,
            total_duration=0.5,
            cost_cents=None,
        ),
    )


class _FakeAgent:
    def __init__(self, act_output=None, batch=None):
        self._act_output = act_output
        self._batch = batch if batch is not None else []
        self.act_calls = []
        self.batch_calls = []

    def act(self, input_data):
        self.act_calls.append(input_data)
        return _agent_response(self._act_output)

    def act_in_batch(self, input_list, iter_func=None):
        self.batch_calls.append(input_list)
        return self._batch


def _patch(monkeypatch, agent):
    monkeypatch.setattr(
        run_mod, "find_config_file", lambda name: Path("/x/config.yml")
    )
    monkeypatch.setattr(
        run_mod,
        "_load_config",
        lambda cf: ({"agent_type": "labeler", "name": "X"}, None),
    )
    monkeypatch.setattr(run_mod, "build_agent", lambda cf, at: agent)


# ── run_agent routing Tests ────────────────────────────────────────


def test_dict_input_routes_through_act(monkeypatch):
    agent = _FakeAgent(act_output={"name": "John"})
    _patch(monkeypatch, agent)

    result = asyncio.run(
        run_agent("X", _FakeRequest({"text": "John is an engineer."}))
    )

    assert agent.act_calls == [{"text": "John is an engineer."}]
    assert agent.batch_calls == []
    assert result["output"] == {"name": "John"}
    assert result["parse_error"] is False


def test_scalar_input_routes_through_batch(monkeypatch):
    # A bare string wrapped as ``input_data`` must not reach act().
    agent = _FakeAgent(batch=[_agent_response({"name": "John"})])
    _patch(monkeypatch, agent)

    result = asyncio.run(
        run_agent("X", _FakeRequest({"input_data": "John is an engineer."}))
    )

    assert agent.act_calls == []
    assert agent.batch_calls == [["John is an engineer."]]
    assert result["output"] == {"name": "John"}
    assert result["parse_error"] is False


def test_scalar_empty_batch_reports_parse_error(monkeypatch):
    # act_in_batch drops unparseable chunks, yielding an empty list.
    agent = _FakeAgent(batch=[])
    _patch(monkeypatch, agent)

    result = asyncio.run(
        run_agent("X", _FakeRequest({"input_data": "gibberish"}))
    )

    assert agent.batch_calls == [["gibberish"]]
    assert result["output"] is None
    assert result["parse_error"] is True
    assert result["metrics"]["tokens"] == 0
