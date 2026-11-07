from dataclasses import asdict
from pathlib import Path

from agents7.call_log import CallLogSummary
from agents7.eval import EvalResult, EvalRun, run_eval_suite
from fastapi import APIRouter, HTTPException

from routers.catalog import find_config_file
from routers.utils import _load_config, agent_unavailable

router = APIRouter(prefix="/api/eval", tags=["eval"])


def _find_golden_set(config_file: Path) -> Path | None:
    """Locate the eval set an agent ships beside its config.

    Prefers the catalog's ``data/golden_set.*`` convention, then
    falls back to an ``eval_data.jsonl`` sitting next to the config
    — the shape a tool agent's trajectory set uses. The order keeps
    agents that ship both on their golden set.

    :param config_file: Path to the agent's YAML config.
    :return: The eval set path, or None when the agent ships none.
    """
    data_dir = config_file.parent / "data"
    candidates = (
        data_dir / "golden_set.csv",
        data_dir / "golden_set.jsonl",
        config_file.parent / "eval_data.jsonl",
    )
    for path in candidates:
        if path.exists():
            return path
    return None


def _trajectory_row(result: EvalResult) -> dict:
    """Shape one trajectory `EvalResult` for the response.

    :param result: An `EvalResult` carrying a `TrajectoryResult`.
    :return: The row payload, with the calls the agent made and the
        expectations it missed or exceeded.
    """
    trajectory = result.trajectory
    return {
        "input": result.input_data,
        "expected": result.expected,
        "actual": result.actual,
        "passed": result.passed,
        "error": result.error,
        "called": [c.format() for c in trajectory.actual]
        if trajectory
        else [],
        "missing": [e.format() for e in trajectory.missing]
        if trajectory
        else [],
        "extra": [c.format() for c in trajectory.extra] if trajectory else [],
    }


def _field_row(result: EvalResult) -> dict:
    """Shape one field-scored `EvalResult` for the response.

    ``error`` is what separates a call that never returned from an
    answer that was simply wrong. Both land in the mismatch list,
    and without it the page renders a failed call as an agent that
    confidently answered nothing.

    :param result: An `EvalResult` scored on output fields.
    :return: The row payload.
    """
    return {
        "input": result.input_data,
        "expected": result.expected,
        "actual": result.actual,
        "passed": result.passed,
        "error": result.error,
        "fields": result.field_results,
    }


def _calls_payload(summary: CallLogSummary | None) -> dict | None:
    """Shape the run's call-log summary for the wire.

    Every field `CallStats` carries is sent, by dumping the
    dataclass rather than listing its fields — the same discipline
    `routers/run.py` uses for `LLMMetrics`, and for the same
    reason: a hand-listed dict is how `cached_prompt_tokens` went
    missing there. The two derived figures are added by name
    because they are properties, not fields.

    :param summary: The run's `CallLogSummary`, or None when the
        agent made no LLM calls (a rule-based one makes none).
    :return: The call totals, or None.
    """
    if summary is None:
        return None
    overall = summary.overall
    return {
        **asdict(overall),
        "success_rate": overall.success_rate,
        "avg_duration": overall.avg_duration,
    }


def _response(run: EvalRun, name: str | None, golden_path: Path) -> dict:
    """Shape a whole run for the Eval page.

    A tool agent is scored on the calls it makes, so its run
    carries a ``trajectory`` block and an empty ``per_category``;
    every other agent type is scored on output fields and carries
    the breakdown instead. The rest of the payload — the totals,
    the per-field accuracy, the timing and the call log — is the
    same for both, because the framework produces it for both.

    :param run: The completed `EvalRun`.
    :param name: The agent's display name from its config.
    :param golden_path: The eval set that was scored.
    :return: The eval response payload.
    """
    trajectory = run.metrics.get("trajectory")
    shape = _trajectory_row if trajectory else _field_row
    rows = [shape(r) for r in run.results]
    return {
        "agent": name,
        "model": run.model_id,
        "golden_set": golden_path.name,
        "fields": run.fields,
        "total": run.metrics["total"],
        "passed": run.metrics["passed"],
        "failed": run.metrics["failed"],
        "accuracy": run.metrics["accuracy"],
        "per_field": run.metrics["per_field"],
        "per_category": run.metrics["per_category"],
        "timing": run.metrics["timing"],
        "trajectory": trajectory,
        "calls": _calls_payload(run.call_log),
        "mismatches": [r for r in rows if not r["passed"]],
    }


@router.post("/{agent_name}")
def eval_agent(agent_name: str) -> dict:
    """Score an agent against the eval set it ships.

    The whole route is `agents7.eval.run_eval_suite` — loading the
    set, building the agent, running every row, comparing the
    answers and aggregating the metrics all belong to the
    framework. This endpoint only finds the files and reshapes the
    finished run for the page.

    :param agent_name: The catalog name of the agent to score.
    :return: The eval response payload.
    :raises HTTPException: 404 when the agent or its eval set
        cannot be found; 422 when the set cannot be scored or the
        agent's own package is not installed.
    """
    config_file = find_config_file(agent_name)
    if config_file is None:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        )

    golden_path = _find_golden_set(config_file)
    if golden_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"No golden set found for agent '{agent_name}'",
        )

    cfg, _ = _load_config(config_file)

    try:
        run = run_eval_suite(config_file, golden_path)
    except ImportError as exc:
        raise agent_unavailable(exc) from exc
    except ValueError as exc:
        # An empty set, an unknown `agent_type`, rows a tool agent's
        # set cannot be scored from — all authoring errors in the
        # agent's own files, not server faults.
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return _response(run, cfg.get("name"), golden_path)
