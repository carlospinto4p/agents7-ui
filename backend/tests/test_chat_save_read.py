"""Tests for saving a live chat session as a read.

The step that joins the Chatter page to the Reads page: a
conversation held in the UI becomes a recording on disk, in the
framework's own shape, so it can be read back and fed back on. At
temperature a re-run is a different conversation, so this has to
capture the one that happened rather than replay it.
"""

import asyncio
from types import SimpleNamespace

import pytest
import routers.chat as chat_mod
from agents7.eval.chat_review import load_recording
from agents7.models.base import LLMMetrics
from fastapi import HTTPException
from routers.chat import (
    _attach_guard_collector,
    _GuardCollector,
    _package_root,
    _package_version,
    _record_turn,
    _store,
    _Transcript,
    save_as_read,
)


def _metrics(**over) -> LLMMetrics:
    base = {
        "tokens": 10,
        "prompt_tokens": 100,
        "cached_prompt_tokens": 90,
        "total_duration": 1.0,
        "cost_cents": 0.01,
    }
    base.update(over)
    return LLMMetrics(**base)


def _resp(text="vale"):
    return SimpleNamespace(response=text, metrics=_metrics())


class _FakeGuarded:
    """A chatter with a `guard_callback` field, as a guarded one has."""

    guard_callback = None

    def _set_attr(self, name, value):
        object.__setattr__(self, name, value)


class _Body:
    """A request whose JSON body is fixed."""

    def __init__(self, data):
        self._data = data

    async def json(self):
        return self._data


@pytest.fixture
def agent_package(tmp_path, monkeypatch):
    """A catalog holding one src-layout agent package."""
    pkg = tmp_path / "demo_agent"
    (pkg / "src" / "demo").mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "demo"\nversion = "2.5.1"\n', encoding="utf-8"
    )
    config = pkg / "src" / "demo" / "config.yml"
    config.write_text("name: demo\n", encoding="utf-8")
    monkeypatch.setattr(chat_mod, "CATALOG_PATH", tmp_path)
    return pkg, config


# ── Locating the package ───────────────────────────────────────────


def test_the_package_root_is_found_from_a_src_layout_config(
    agent_package,
):
    pkg, config = agent_package
    assert _package_root(config) == pkg.resolve()


def test_the_version_comes_from_the_package_not_the_config(
    agent_package,
):
    """`Chatter.version` is the config SCHEMA version — a recording
    came out stamped `1` that way once."""
    _, config = agent_package
    assert _package_version(config) == "2.5.1"


def test_a_config_with_no_package_falls_back_to_its_own_folder(
    tmp_path, monkeypatch
):
    """A sample ships no `pyproject.toml`."""
    monkeypatch.setattr(chat_mod, "CATALOG_PATH", tmp_path)
    sample = tmp_path / "examples" / "thing"
    sample.mkdir(parents=True)
    config = sample / "config.yml"
    config.write_text("name: thing\n", encoding="utf-8")
    assert _package_root(config) == sample.resolve()
    assert _package_version(config) == "unknown"


def test_an_unreadable_manifest_reports_unknown(agent_package):
    pkg, config = agent_package
    (pkg / "pyproject.toml").write_text("not [ toml", encoding="utf-8")
    assert _package_version(config) == "unknown"


# ── The guard collector keeps whole events ─────────────────────────


def test_the_collector_keeps_the_guard_verdicts():
    """Summing them to a cost was enough only while the metrics
    line was the one consumer; a saved read needs the reasons."""
    guarded = _FakeGuarded()
    _attach_guard_collector(guarded)
    guarded.guard_callback(
        SimpleNamespace(
            attempt=0,
            accepted=False,
            reason=SimpleNamespace(value="off-topic"),
            response_text="nope",
            fix="better",
            used_fix=False,
            parse_failed=False,
            metrics=_metrics(),
        )
    )
    attempts = guarded.guard_callback.attempts()
    assert len(attempts) == 1
    assert attempts[0].accepted is False
    assert attempts[0].reason == "off-topic"
    assert attempts[0].fix == "better"


def test_the_collector_still_totals_the_cost():
    collector = _GuardCollector()
    collector(SimpleNamespace(metrics=_metrics(cost_cents=0.5)))
    collector(SimpleNamespace(metrics=_metrics(cost_cents=0.25)))
    assert collector.summary()["calls"] == 2


def test_an_event_with_no_metrics_still_becomes_an_attempt():
    """Using the guard's fix verbatim costs no call, but the
    rejection it came from is still part of the turn."""
    collector = _GuardCollector()
    collector(
        SimpleNamespace(
            attempt=0,
            accepted=False,
            reason="off-topic",
            response_text="nope",
            fix="better",
            used_fix=True,
            parse_failed=False,
            metrics=None,
        )
    )
    assert collector.summary() is None
    assert len(collector.attempts()) == 1
    assert collector.attempts()[0].metrics is None


# ── Recording turns ────────────────────────────────────────────────


def _transcript(config):
    return _Transcript(
        agent="demo",
        agent_version="2.5.1",
        config_file=config,
        context={"nick": "Marta_87"},
        facts=("Le gusta llegar el último.",),
        recorded="2026-09-20T10:00:00+00:00",
    )


def test_an_opening_turn_records_no_prompt(agent_package):
    _, config = agent_package
    t = _transcript(config)
    t.record(None, _resp("buenas"), (), 1.2)
    assert t.turns[0].prompt is None
    assert t.turns[0].reply == "buenas"


def test_turns_are_indexed_in_order(agent_package):
    _, config = agent_package
    t = _transcript(config)
    t.record(None, _resp("buenas"), (), 1.0)
    t.record("hola", _resp("qué tal"), (), 1.0)
    assert [turn.index for turn in t.turns] == [0, 1]


def test_a_stream_that_produced_nothing_records_nothing(agent_package):
    """`chat_response` is None until the stream is drained."""
    _, config = agent_package
    t = _transcript(config)
    t.record("hola", None, (), 1.0)
    assert t.turns == []


def test_recording_never_raises_into_a_chat(agent_package, monkeypatch):
    """A turn must still be answered if the transcript fails."""
    _, config = agent_package
    t = _transcript(config)
    monkeypatch.setattr(
        t, "record", lambda *a, **k: (_ for _ in ()).throw(RuntimeError())
    )
    sid = _store.create(_FakeGuarded(), t)
    try:
        _record_turn(sid, "hola", _resp(), _FakeGuarded(), 1.0)
    finally:
        _store.delete(sid)


def test_a_session_with_no_transcript_is_skipped():
    sid = _store.create(_FakeGuarded())
    try:
        _record_turn(sid, "hola", _resp(), _FakeGuarded(), 1.0)
    finally:
        _store.delete(sid)


# ── Saving ─────────────────────────────────────────────────────────


@pytest.fixture
def session(agent_package):
    _, config = agent_package
    t = _transcript(config)
    t.record(None, _resp("buenas"), (), 1.0)
    t.record("hola", _resp("qué tal"), (), 1.0)
    sid = _store.create(_FakeGuarded(), t)
    yield sid, config
    _store.delete(sid)


def _save(session_id, **body):
    """Call the endpoint the way this project drives async routes."""
    return asyncio.run(save_as_read(session_id, _Body(body)))


def test_saving_writes_a_recording_the_reads_page_can_load(
    session, agent_package
):
    pkg, _ = agent_package
    sid, _ = session
    body = _save(sid, read_id="2026-09-20", conversation_id="warm")
    target = pkg / "docs" / "reads" / "2026-09-20" / "warm.json"
    saved = load_recording(target)
    assert saved.conversation_id == "warm"
    assert [t.reply for t in saved.turns] == ["buenas", "qué tal"]
    assert body["turns"] == 2


def test_the_saved_read_carries_the_context_and_facts(session, agent_package):
    pkg, _ = agent_package
    sid, _ = session
    _save(sid, read_id="r", conversation_id="c")
    saved = load_recording(pkg / "docs" / "reads" / "r" / "c.json")
    assert saved.context == {"nick": "Marta_87"}
    assert saved.facts == ("Le gusta llegar el último.",)


def test_the_saved_read_is_stamped_with_the_package_version(
    session, agent_package
):
    pkg, _ = agent_package
    sid, _ = session
    _save(sid, read_id="r", conversation_id="c")
    saved = load_recording(pkg / "docs" / "reads" / "r" / "c.json")
    assert saved.agent_version == "2.5.1"


def test_saving_returns_the_path_the_reads_page_uses(session):
    sid, _ = session
    body = _save(sid, read_id="r", conversation_id="c")
    assert body["path"] == "demo_agent/docs/reads/r"


def test_the_read_id_defaults_to_today(session):
    from datetime import UTC, datetime

    sid, _ = session
    body = _save(sid)
    assert body["read_id"] == datetime.now(UTC).date().isoformat()
    assert body["conversation_id"] == "chat"


def test_an_existing_recording_is_never_overwritten(session):
    """A recording is paid for and cannot be re-made."""
    sid, _ = session
    _save(sid, read_id="r", conversation_id="c")
    with pytest.raises(HTTPException) as exc:
        _save(sid, read_id="r", conversation_id="c")
    assert exc.value.status_code == 409


def test_saving_leaves_the_session_open(session):
    """A snapshot, not an ending — the chat can continue."""
    sid, _ = session
    _save(sid, read_id="r", conversation_id="c")
    assert _store.get(sid) is not None
    assert _store.transcript(sid) is not None


@pytest.mark.parametrize("bad", ["../escape", "a/b", "x" * 65, "a b"])
def test_a_name_that_could_escape_the_folder_is_refused(session, bad):
    sid, _ = session
    with pytest.raises(HTTPException) as exc:
        _save(sid, read_id=bad)
    assert exc.value.status_code == 400


def test_a_bad_conversation_id_is_refused_too(session):
    sid, _ = session
    with pytest.raises(HTTPException) as exc:
        _save(sid, read_id="r", conversation_id="../escape")
    assert exc.value.status_code == 400


def test_a_session_that_said_nothing_cannot_be_saved(agent_package):
    _, config = agent_package
    sid = _store.create(_FakeGuarded(), _transcript(config))
    try:
        with pytest.raises(HTTPException) as exc:
            _save(sid)
        assert exc.value.status_code == 422
    finally:
        _store.delete(sid)


def test_an_unknown_session_is_a_404():
    with pytest.raises(HTTPException) as exc:
        _save("nope")
    assert exc.value.status_code == 404
