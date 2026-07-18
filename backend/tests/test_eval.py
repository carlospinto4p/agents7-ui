"""Tests for the eval endpoint's tool-agent route.

A tool agent is scored on the calls it makes, not on output fields,
so the endpoint hands the whole route to
`agents7.eval.run_eval_suite` and only reshapes the run for the UI.
These tests lock in that delegation and the response shape.
"""

from pathlib import Path

import pytest
from agents7.eval.metrics import EvalResult
from agents7.eval.trajectory import (
    ExpectedCall,
    ToolCall,
    TrajectoryMode,
    match_trajectory,
)
from fastapi import HTTPException

import routers.eval as eval_mod
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


# ── Tool-agent eval Tests ──────────────────────────────────────────


def _result(expected_names, actual_calls, mode=TrajectoryMode.IN_ORDER):
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


class _FakeRun:
    def __init__(self, results, metrics):
        self.results = results
        self.metrics = metrics


def _patch_eval(monkeypatch, run=None, raises=None, tmp_path=None):
    golden = tmp_path / "eval_data.jsonl"
    golden.touch()
    monkeypatch.setattr(
        eval_mod, "find_config_file", lambda name: tmp_path / "config.yml"
    )
    monkeypatch.setattr(eval_mod, "_find_golden_set", lambda cf: golden)
    monkeypatch.setattr(
        eval_mod,
        "_load_config",
        lambda cf: ({"agent_type": "tool", "name": "StoreAssistant"}, None),
    )

    def _suite(config, data):
        if raises is not None:
            raise raises
        return run

    monkeypatch.setattr(eval_mod, "run_eval_suite", _suite)
    return golden


def test_tool_eval_reports_trajectory_metrics(monkeypatch, tmp_path):
    """The framework's trajectory block is passed through intact."""
    passing = _result(["find_product"], [("find_product", {})])
    failing = _result(["check_stock"], [("find_product", {})])
    metrics = {
        "total": 2,
        "passed": 1,
        "failed": 1,
        "accuracy": 0.5,
        "trajectory": {
            "mode": "in_order",
            "expected_calls": 2,
            "matched_calls": 1,
            "extra_calls": 1,
            "per_tool": {
                "check_stock": {"expected": 1, "matched": 0},
                "find_product": {"expected": 1, "matched": 1},
            },
        },
    }
    _patch_eval(
        monkeypatch,
        run=_FakeRun([passing, failing], metrics),
        tmp_path=tmp_path,
    )

    result = eval_agent("StoreAssistant")

    assert result["total"] == 2
    assert result["passed"] == 1
    assert result["accuracy"] == 0.5
    assert result["trajectory"] == metrics["trajectory"]
    # A trajectory has no categorical field to cross-tabulate.
    assert result["per_category"] == {}


def test_tool_eval_mismatch_carries_missing_and_extra(monkeypatch, tmp_path):
    """A failed row names the calls it missed and the ones it added."""
    failing = _result(["check_stock"], [("find_product", {"q": "mug"})])
    metrics = {
        "total": 1,
        "passed": 0,
        "failed": 1,
        "accuracy": 0.0,
        "trajectory": {"mode": "in_order", "per_tool": {}},
    }
    _patch_eval(
        monkeypatch, run=_FakeRun([failing], metrics), tmp_path=tmp_path
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
    passing = _result(["find_product"], [("find_product", {})])
    metrics = {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "accuracy": 1.0,
        "trajectory": {"mode": "in_order", "per_tool": {}},
    }
    _patch_eval(
        monkeypatch, run=_FakeRun([passing], metrics), tmp_path=tmp_path
    )

    assert eval_agent("StoreAssistant")["mismatches"] == []


def test_tool_eval_surfaces_bad_golden_set_as_422(monkeypatch, tmp_path):
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
