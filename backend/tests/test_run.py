"""Tests for the single-run endpoint's input routing.

The framework's single ``act()`` only accepts a dict, while a bare
scalar (a single free-text string, as several catalog agents use) must
go through ``act_in_batch`` — the same path eval uses. These tests lock
that routing in.

A tool agent takes neither route: it answers in free text and is run
through ``act_stream`` so its trajectory is reported alongside the
answer. Those tests live at the bottom of this module.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
import routers.run as run_mod
from agents7.agents.tool_agent import ToolStepEvent, ToolStepKind
from agents7.exceptions import ToolLoopError
from agents7.models import LLMMetrics
from fastapi import HTTPException
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
        metrics=LLMMetrics(
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


# ── Tool agent Tests ───────────────────────────────────────────────


def _tool_events():
    """The event sequence a one-tool loop yields."""
    return [
        ToolStepEvent(
            kind=ToolStepKind.TOOL_CALL,
            iteration=0,
            name="find_product",
            arguments={"query": "blue mug"},
        ),
        ToolStepEvent(
            kind=ToolStepKind.TOOL_RESULT,
            iteration=0,
            name="find_product",
            result='{"sku": "MUG-01"}',
        ),
        ToolStepEvent(
            kind=ToolStepKind.ANSWER,
            iteration=1,
            text="We have blue mugs.",
            thinking="checked the catalog",
        ),
    ]


class _FakeStream:
    """Stand-in for `ToolStreamResult`.

    Yields *events*, then exposes the final response — or raises
    *raises* partway through, as an exhausted loop does.
    """

    def __init__(self, events, response=None, raises=None):
        self._events = events
        self._raises = raises
        self.agent_response = response

    def __iter__(self):
        yield from self._events
        if self._raises is not None:
            raise self._raises


class _FakeToolAgent:
    def __init__(self, stream):
        self._stream = stream
        self.stream_calls = []

    def act_stream(self, user_input):
        self.stream_calls.append(user_input)
        return self._stream


def _patch_tool(monkeypatch, agent):
    monkeypatch.setattr(
        run_mod, "find_config_file", lambda name: Path("/x/config.yml")
    )
    monkeypatch.setattr(
        run_mod,
        "_load_config",
        lambda cf: ({"agent_type": "tool", "name": "StoreAssistant"}, None),
    )
    monkeypatch.setattr(run_mod, "build_agent", lambda cf, at: agent)


def test_tool_agent_returns_answer_and_trajectory(monkeypatch):
    """The answer is served as `answer`, with every step reported."""
    response = SimpleNamespace(
        response="We have blue mugs.",
        thinking="checked the catalog",
        metrics=LLMMetrics(
            tokens=42, prompt_tokens=20, total_duration=1.5, cost_cents=None
        ),
    )
    agent = _FakeToolAgent(_FakeStream(_tool_events(), response=response))
    _patch_tool(monkeypatch, agent)

    result = asyncio.run(
        run_agent("X", _FakeRequest({"input_data": "Any blue mugs?"}))
    )

    assert agent.stream_calls == ["Any blue mugs?"]
    assert result["answer"] == "We have blue mugs."
    assert result["thinking"] == "checked the catalog"
    assert result["parse_error"] is False
    assert result["error"] is None
    assert result["metrics"]["tokens"] == 42
    assert [s["kind"] for s in result["tool_steps"]] == [
        "tool_call",
        "tool_result",
        "answer",
    ]


def test_tool_step_payload_omits_unset_fields(monkeypatch):
    """A call carries arguments, a result carries its result."""
    agent = _FakeToolAgent(_FakeStream(_tool_events()))
    _patch_tool(monkeypatch, agent)

    result = asyncio.run(
        run_agent("X", _FakeRequest({"input_data": "Any blue mugs?"}))
    )

    call, tool_result, answer = result["tool_steps"]
    assert call["arguments"] == {"query": "blue mug"}
    assert "result" not in call
    assert tool_result["result"] == '{"sku": "MUG-01"}'
    assert "arguments" not in tool_result
    assert "error" not in tool_result
    assert answer == {"kind": "answer", "iteration": 1}


def test_tool_step_payload_carries_a_rejected_call(monkeypatch):
    """A call the tool threw out is flagged, not just described.

    `result` is the "Error: ..." text the model was handed, and a
    tool may return text starting with "Error:" and have succeeded
    — so `error` is what the page needs to render the failure.
    """
    events = [
        ToolStepEvent(
            kind=ToolStepKind.TOOL_CALL,
            iteration=0,
            name="find_product",
            arguments={"query": {"type": "string", "value": "mug"}},
        ),
        ToolStepEvent(
            kind=ToolStepKind.TOOL_RESULT,
            iteration=0,
            name="find_product",
            result="Error: Invalid arguments for `find_product`",
            error="Invalid arguments for `find_product`",
        ),
        ToolStepEvent(
            kind=ToolStepKind.ANSWER,
            iteration=1,
            text="Sorry, I could not find that.",
        ),
    ]
    agent = _FakeToolAgent(_FakeStream(events))
    _patch_tool(monkeypatch, agent)

    result = asyncio.run(
        run_agent("X", _FakeRequest({"input_data": "Any blue mugs?"}))
    )

    tool_result = result["tool_steps"][1]
    assert tool_result["error"] == "Invalid arguments for `find_product`"
    assert tool_result["result"].startswith("Error: Invalid arguments")


def test_tool_loop_error_reports_steps_made(monkeypatch):
    """An exhausted loop returns its calls, not a 500."""
    events = _tool_events()[:2]
    agent = _FakeToolAgent(
        _FakeStream(events, raises=ToolLoopError("exceeded 6 iterations"))
    )
    _patch_tool(monkeypatch, agent)

    result = asyncio.run(
        run_agent("X", _FakeRequest({"input_data": "Any blue mugs?"}))
    )

    assert result["error"] == "exceeded 6 iterations"
    assert result["parse_error"] is True
    assert result["answer"] is None
    assert len(result["tool_steps"]) == 2
    assert result["metrics"]["tokens"] == 0


def test_tool_agent_rejects_dict_input(monkeypatch):
    """A field dict is a client error, not a silent stringification."""
    agent = _FakeToolAgent(_FakeStream([]))
    _patch_tool(monkeypatch, agent)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(run_agent("X", _FakeRequest({"text": "Any blue mugs?"})))

    assert exc.value.status_code == 422
    assert "must be a string" in exc.value.detail
    assert agent.stream_calls == []


# ── Missing agent package Tests ────────────────────────────────────


def _patch_build_importing(monkeypatch, agent_type, dotted):
    """Patch `build_agent` to fail the way a real config would.

    The failure is produced by actually resolving *dotted* through
    the framework's `import_from_path`, so the `ModuleNotFoundError`
    carries the `name` attribute the interpreter sets — a hand-built
    exception does not, and would let the test pass against a
    message that never names the module.
    """
    monkeypatch.setattr(
        run_mod, "find_config_file", lambda name: Path("/x/config.yml")
    )
    monkeypatch.setattr(
        run_mod,
        "_load_config",
        lambda cf: ({"agent_type": agent_type, "name": "X"}, None),
    )

    def _build(config_file, at):
        from agents7.agents.utils import import_from_path

        return import_from_path(dotted)

    monkeypatch.setattr(run_mod, "build_agent", _build)


def test_missing_package_is_422_not_500(monkeypatch):
    """A catalog agent whose own package is absent must not 500.

    A config naming `my_tagger.models.Tag` makes building it raise
    `ModuleNotFoundError` from inside `from_yaml` when that package
    is not installed here.
    """
    _patch_build_importing(
        monkeypatch, "labeler", "my_tagger_absent.models.Tag"
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(run_agent("X", _FakeRequest({"input_data": "david"})))

    assert exc.value.status_code == 422
    assert "my_tagger_absent" in exc.value.detail
    assert "not installed" in exc.value.detail


def test_tool_agent_missing_package_is_422(monkeypatch):
    _patch_build_importing(
        monkeypatch, "tool", "store_tools_absent.tools.find_product"
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(run_agent("X", _FakeRequest({"input_data": "hi"})))

    assert exc.value.status_code == 422
    assert "store_tools_absent" in exc.value.detail


def test_run_metrics_carry_the_cache_flag(monkeypatch):
    """A cached run must be tellable from a fast free one.

    Three of the six metrics payloads in this router were built by
    hand and had drifted, dropping `cached_prompt_tokens` and
    `cached` — so a run served from the response cache rendered as
    a real call that took no time and cost nothing.
    """
    cached = _agent_response({"name": "John"})
    cached.metrics = LLMMetrics(
        tokens=7,
        prompt_tokens=3,
        cached_prompt_tokens=3,
        total_duration=0.0004,
        cost_cents=0.0,
        cached=True,
    )
    agent = _FakeAgent()
    agent.act = lambda input_data: cached
    _patch(monkeypatch, agent)

    result = asyncio.run(
        run_agent("X", _FakeRequest({"text": "John is an engineer."}))
    )

    assert result["metrics"]["cached"] is True
    assert result["metrics"]["cached_prompt_tokens"] == 3


def test_run_metrics_carry_the_retries(monkeypatch):
    """A run that fought the provider must not look clean.

    The retry seconds sit outside `total_duration`, which is the
    successful attempt's own figure, so a run that spent a minute
    on backoff would otherwise render as a quick one.
    """
    retried = _agent_response({"name": "John"})
    retried.metrics = LLMMetrics(
        tokens=7,
        prompt_tokens=3,
        total_duration=1.2,
        retries=2,
        retry_duration=6.0,
    )
    agent = _FakeAgent()
    agent.act = lambda input_data: retried
    _patch(monkeypatch, agent)

    result = asyncio.run(
        run_agent("X", _FakeRequest({"text": "John is an engineer."}))
    )

    assert result["metrics"]["retries"] == 2
    assert result["metrics"]["retry_duration"] == 6.0


def test_a_run_that_produced_nothing_is_unpriced_not_free(monkeypatch):
    """No measurement is not a measurement of zero.

    A tool loop that exceeded `max_iterations` never produced an
    `AgentResponse`, so its cost is unknown — `None`, never `0.0`,
    which would read as a run that really happened and was free.
    """
    empty = run_mod._tool_metrics(None)

    # Compared against the framework's own zero rather than a
    # hand-written dict, so a metric added upstream does not have
    # to be remembered here as well.
    assert (
        empty
        == LLMMetrics(
            tokens=0, prompt_tokens=0, total_duration=0.0
        ).model_dump()
    )
    assert empty["cost_cents"] is None
