"""Tests for the eval endpoint.

Every agent type is scored by `agents7.eval.run_eval_suite`; the
endpoint finds the config and the eval set and reshapes the finished
run for the page. These tests lock in that delegation and the two
response shapes — trajectory for a tool agent, output fields for
everything else.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
import routers.eval as eval_mod
from agents7.call_log import CallLogSummary, CallStats
from agents7.eval.metrics import EvalResult
from agents7.eval.trajectory import (
    ExpectedCall,
    ToolCall,
    TrajectoryMode,
    match_trajectory,
)
from fastapi import HTTPException
from routers.eval import _find_golden_set, eval_agent

# ── _find_golden_set ───────────────────────────────────────────────


def test_finds_golden_set_in_data_dir(tmp_path):
    config = tmp_path / "config.yml"
    config.touch()
    (tmp_path / "data").mkdir()
    golden = tmp_path / "data" / "golden_set.jsonl"
    golden.touch()

    assert _find_golden_set(config) == golden


def test_falls_back_to_eval_data_beside_config(tmp_path):
    """A tool agent's trajectory set ships next to the config."""
    config = tmp_path / "config.yml"
    config.touch()
    eval_data = tmp_path / "eval_data.jsonl"
    eval_data.touch()

    assert _find_golden_set(config) == eval_data


def test_golden_set_wins_over_eval_data(tmp_path):
    """An agent shipping both keeps scoring its golden set."""
    config = tmp_path / "config.yml"
    config.touch()
    (tmp_path / "data").mkdir()
    golden = tmp_path / "data" / "golden_set.csv"
    golden.touch()
    (tmp_path / "eval_data.jsonl").touch()

    assert _find_golden_set(config) == golden


def test_returns_none_when_no_eval_set(tmp_path):
    config = tmp_path / "config.yml"
    config.touch()

    assert _find_golden_set(config) is None


# ── Fixtures shared by both scoring shapes ─────────────────────────

_METRIC_KEYS = ("total", "passed", "failed", "accuracy")


def _metrics(total, passed, **extra):
    """A `compute_metrics` result, with the defaults filled in."""
    base = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": passed / total if total else 0.0,
        "per_field": {},
        "per_category": {},
        "timing": {
            "total_s": 0.0,
            "avg_s": 0.0,
            "min_s": 0.0,
            "max_s": 0.0,
            "per_case": [],
        },
    }
    base.update(extra)
    return base


@dataclass
class _FakeRun:
    """Stands in for the `EvalRun` `run_eval_suite` returns."""

    results: list
    metrics: dict
    model_id: str = "ollama::gemma4:12b"
    fields: list | None = None
    call_log: CallLogSummary | None = None

    def __post_init__(self):
        if self.fields is None:
            self.fields = ["category"]


def _patch_eval(
    monkeypatch,
    run=None,
    raises=None,
    tmp_path=None,
    agent_type="tool",
    name="StoreAssistant",
):
    """Point the endpoint at a fake run, capturing its arguments."""
    golden = tmp_path / "eval_data.jsonl"
    golden.touch()
    monkeypatch.setattr(
        eval_mod, "find_config_file", lambda n: tmp_path / "config.yml"
    )
    monkeypatch.setattr(eval_mod, "_find_golden_set", lambda cf: golden)
    monkeypatch.setattr(
        eval_mod,
        "_load_config",
        lambda cf: ({"agent_type": agent_type, "name": name}, None),
    )

    calls = []

    def _suite(config, data):
        calls.append((config, data))
        if raises is not None:
            raise raises
        return run

    monkeypatch.setattr(eval_mod, "run_eval_suite", _suite)
    return calls


# ── Tool-agent (trajectory) Tests ──────────────────────────────────


def _trajectory_result(
    expected_names, actual_calls, mode=TrajectoryMode.IN_ORDER
):
    """Build an `EvalResult` carrying a matched trajectory."""
    expected = [ExpectedCall(name=n) for n in expected_names]
    actual = [ToolCall(name=n, arguments=a) for n, a in actual_calls]
    trajectory = match_trajectory(expected, actual, mode)

    result = EvalResult(
        input_data="Any blue mugs?",
        expected={"tools": [e.format() for e in expected]},
    )
    result.actual = {"tools": [c.format() for c in actual]}
    result.trajectory = trajectory
    result.passed = trajectory.passed
    return result


def test_tool_eval_reports_trajectory_metrics(monkeypatch, tmp_path):
    """The framework's trajectory block is passed through intact."""
    passing = _trajectory_result(["find_product"], [("find_product", {})])
    failing = _trajectory_result(["check_stock"], [("find_product", {})])
    trajectory = {
        "mode": "in_order",
        "expected_calls": 2,
        "matched_calls": 1,
        "extra_calls": 1,
        "per_tool": {
            "check_stock": {"expected": 1, "matched": 0},
            "find_product": {"expected": 1, "matched": 1},
        },
    }
    _patch_eval(
        monkeypatch,
        run=_FakeRun(
            [passing, failing], _metrics(2, 1, trajectory=trajectory)
        ),
        tmp_path=tmp_path,
    )

    result = eval_agent("StoreAssistant")

    assert result["total"] == 2
    assert result["passed"] == 1
    assert result["accuracy"] == 0.5
    assert result["trajectory"] == trajectory
    # A trajectory has no categorical field to cross-tabulate.
    assert result["per_category"] == {}


def test_tool_eval_mismatch_carries_missing_and_extra(monkeypatch, tmp_path):
    """A failed row names the calls it missed and the ones it added."""
    failing = _trajectory_result(
        ["check_stock"], [("find_product", {"q": "mug"})]
    )
    _patch_eval(
        monkeypatch,
        run=_FakeRun(
            [failing],
            _metrics(1, 0, trajectory={"mode": "in_order", "per_tool": {}}),
        ),
        tmp_path=tmp_path,
    )

    result = eval_agent("StoreAssistant")

    assert len(result["mismatches"]) == 1
    row = result["mismatches"][0]
    assert row["input"] == "Any blue mugs?"
    assert row["called"] == ["find_product(q='mug')"]
    assert row["missing"] == ["check_stock(…)"]
    assert row["extra"] == ["find_product(q='mug')"]
    assert row["passed"] is False


def test_tool_eval_omits_passing_rows_from_mismatches(monkeypatch, tmp_path):
    passing = _trajectory_result(["find_product"], [("find_product", {})])
    _patch_eval(
        monkeypatch,
        run=_FakeRun(
            [passing],
            _metrics(1, 1, trajectory={"mode": "in_order", "per_tool": {}}),
        ),
        tmp_path=tmp_path,
    )

    assert eval_agent("StoreAssistant")["mismatches"] == []


# ── Field-scored Tests ─────────────────────────────────────────────


def _field_result(expected, actual, error=None):
    """Build a field-scored `EvalResult`."""
    result = EvalResult(
        input_data={"text": "jessica_2001"},
        expected={"category": expected},
    )
    result.actual = actual
    result.error = error
    result.field_results = (
        {} if actual is None else {"category": actual["category"] == expected}
    )
    result.passed = all(result.field_results.values()) if actual else False
    return result


def test_field_eval_delegates_to_the_suite(monkeypatch, tmp_path):
    """A labeler goes through `run_eval_suite`, not a local loop.

    The hand-rolled branch this replaced duplicated
    `run_evaluation` and `compute_metrics`, and had already
    drifted from the framework's own field comparison.
    """
    passing = _field_result("FEMALE", {"category": "FEMALE"})
    failing = _field_result("FEMALE", {"category": "MALE"})
    calls = _patch_eval(
        monkeypatch,
        run=_FakeRun(
            [passing, failing],
            _metrics(
                2,
                1,
                per_field={"category": 0.5},
                per_category={
                    "FEMALE": {"total": 2, "passed": 1, "accuracy": 0.5}
                },
            ),
        ),
        tmp_path=tmp_path,
        agent_type="labeler",
        name="MyTagger",
    )

    result = eval_agent("MyTagger")

    assert len(calls) == 1
    assert result["agent"] == "MyTagger"
    assert all(k in result for k in _METRIC_KEYS)
    assert result["accuracy"] == 0.5
    # A field-scored run has no trajectory block.
    assert result["trajectory"] is None


def test_field_eval_carries_per_field_and_timing(monkeypatch, tmp_path):
    """Two figures the hand-rolled branch computed and discarded."""
    timing = {
        "total_s": 4.0,
        "avg_s": 2.0,
        "min_s": 1.5,
        "max_s": 2.5,
        "per_case": [1.5, 2.5],
    }
    _patch_eval(
        monkeypatch,
        run=_FakeRun(
            [_field_result("FEMALE", {"category": "FEMALE"})],
            _metrics(
                1,
                1,
                per_field={"category": 1.0, "reason": 0.5},
                timing=timing,
            ),
        ),
        tmp_path=tmp_path,
        agent_type="labeler",
    )

    result = eval_agent("MyTagger")

    assert result["per_field"] == {"category": 1.0, "reason": 0.5}
    assert result["timing"] == timing


def test_field_eval_distinguishes_an_error_from_a_wrong_answer(
    monkeypatch, tmp_path
):
    """A row the agent could not answer says so.

    Both land in the mismatch list; without `error` the page
    renders a failed call as an agent that answered nothing.
    """
    wrong = _field_result("FEMALE", {"category": "MALE"})
    crashed = _field_result("FEMALE", None, error="Connection refused")
    _patch_eval(
        monkeypatch,
        run=_FakeRun([wrong, crashed], _metrics(2, 0)),
        tmp_path=tmp_path,
        agent_type="labeler",
    )

    rows = eval_agent("MyTagger")["mismatches"]

    assert len(rows) == 2
    assert rows[0]["error"] is None
    assert rows[0]["actual"] == {"category": "MALE"}
    assert rows[1]["error"] == "Connection refused"
    assert rows[1]["actual"] is None


def test_field_eval_reports_what_the_run_cost(monkeypatch, tmp_path):
    """Tokens, duration and cost reach the page.

    Nothing passed a call log before, so the run had no summary
    to report and the page could not say what an eval cost.
    """
    stats = CallStats(
        calls=2,
        successes=2,
        tokens=40,
        prompt_tokens=120,
        cached_prompt_tokens=100,
        total_duration=4.0,
        cost_cents=0.0125,
        cached_calls=1,
        retries=1,
        retry_duration=2.0,
        retried_calls=1,
    )
    _patch_eval(
        monkeypatch,
        run=_FakeRun(
            [_field_result("FEMALE", {"category": "FEMALE"})],
            _metrics(1, 1),
            call_log=CallLogSummary(overall=stats),
        ),
        tmp_path=tmp_path,
        agent_type="labeler",
    )

    calls = eval_agent("MyTagger")["calls"]

    assert calls["calls"] == 2
    assert calls["tokens"] == 40
    assert calls["cached_prompt_tokens"] == 100
    assert calls["total_duration"] == 4.0
    assert calls["cost_cents"] == 0.0125
    assert calls["cached_calls"] == 1
    assert calls["retries"] == 1
    assert calls["retry_duration"] == 2.0
    assert calls["avg_duration"] == 2.0
    assert calls["success_rate"] == 1.0


def test_call_payload_carries_every_field_call_stats_has(
    monkeypatch, tmp_path
):
    """The payload mirrors the measurement surface.

    Listing the fields by hand is how `cached_prompt_tokens` went
    missing from three of the Runner's payloads; this fails if a
    new `CallStats` field is not carried through.
    """
    _patch_eval(
        monkeypatch,
        run=_FakeRun(
            [_field_result("FEMALE", {"category": "FEMALE"})],
            _metrics(1, 1),
            call_log=CallLogSummary(overall=CallStats(calls=1)),
        ),
        tmp_path=tmp_path,
        agent_type="labeler",
    )

    calls = eval_agent("MyTagger")["calls"]

    missing = {f for f in CallStats.__dataclass_fields__ if f not in calls}
    assert missing == set()


def test_unpriced_run_reports_none_not_zero(monkeypatch, tmp_path):
    """An Ollama run is unpriced, which is not the same as free."""
    _patch_eval(
        monkeypatch,
        run=_FakeRun(
            [_field_result("FEMALE", {"category": "FEMALE"})],
            _metrics(1, 1),
            call_log=CallLogSummary(
                overall=CallStats(calls=1, cost_cents=None)
            ),
        ),
        tmp_path=tmp_path,
        agent_type="labeler",
    )

    assert eval_agent("MyTagger")["calls"]["cost_cents"] is None


def test_rule_based_agent_reports_no_calls(monkeypatch, tmp_path):
    """An agent that makes no LLM call has nothing to summarise."""
    _patch_eval(
        monkeypatch,
        run=_FakeRun(
            [_field_result("FEMALE", {"category": "FEMALE"})],
            _metrics(1, 1),
        ),
        tmp_path=tmp_path,
        agent_type="labeler",
    )

    assert eval_agent("MyTagger")["calls"] is None


# ── Error routes ───────────────────────────────────────────────────


def test_bad_golden_set_surfaces_as_422(monkeypatch, tmp_path):
    """A set with no `tools` column is an authoring error, not a 500."""
    _patch_eval(
        monkeypatch,
        raises=ValueError("`eval_data.jsonl` has no `tools` column"),
        tmp_path=tmp_path,
    )

    with pytest.raises(HTTPException) as exc:
        eval_agent("StoreAssistant")

    assert exc.value.status_code == 422
    assert "no `tools` column" in exc.value.detail


def test_unknown_agent_type_is_422(monkeypatch, tmp_path):
    """The framework rejects the type; the endpoint relays it."""
    _patch_eval(
        monkeypatch,
        raises=ValueError("Unknown agent_type 'wizard' — must be one of"),
        tmp_path=tmp_path,
        agent_type="wizard",
    )

    with pytest.raises(HTTPException) as exc:
        eval_agent("StoreAssistant")

    assert exc.value.status_code == 422
    assert "wizard" in exc.value.detail


def test_missing_agent_is_404(monkeypatch):
    monkeypatch.setattr(eval_mod, "find_config_file", lambda name: None)

    with pytest.raises(HTTPException) as exc:
        eval_agent("nope")

    assert exc.value.status_code == 404


def test_missing_golden_set_is_404(monkeypatch):
    monkeypatch.setattr(
        eval_mod, "find_config_file", lambda name: Path("/x/config.yml")
    )
    monkeypatch.setattr(eval_mod, "_find_golden_set", lambda cf: None)

    with pytest.raises(HTTPException) as exc:
        eval_agent("X")

    assert exc.value.status_code == 404


# ── Missing agent package Tests ────────────────────────────────────


def _real_import_error(dotted):
    """Return the `ModuleNotFoundError` importing *dotted* raises.

    Produced by a real import so the exception carries the `name`
    attribute the interpreter sets; a hand-built one does not, and
    the message would then never name the missing module.
    """
    from agents7.agents.utils import import_from_path

    try:
        import_from_path(dotted)
    except ModuleNotFoundError as exc:
        return exc
    raise AssertionError(f"{dotted} unexpectedly imported")


def test_tool_eval_missing_package_is_422(monkeypatch, tmp_path):
    """An agent whose own package is absent is not a 500."""
    _patch_eval(
        monkeypatch,
        raises=_real_import_error("store_tools_absent.tools.find_product"),
        tmp_path=tmp_path,
    )

    with pytest.raises(HTTPException) as exc:
        eval_agent("StoreAssistant")

    assert exc.value.status_code == 422
    assert "store_tools_absent" in exc.value.detail
    assert "not installed" in exc.value.detail


def test_field_eval_missing_package_is_422(monkeypatch, tmp_path):
    """The same holds for a field-scored agent, on the same route."""
    _patch_eval(
        monkeypatch,
        raises=_real_import_error("my_tagger_absent.models.Tag"),
        tmp_path=tmp_path,
        agent_type="labeler",
        name="MyTagger",
    )

    with pytest.raises(HTTPException) as exc:
        eval_agent("MyTagger")

    assert exc.value.status_code == 422
    assert "my_tagger_absent" in exc.value.detail
    assert "not installed" in exc.value.detail
