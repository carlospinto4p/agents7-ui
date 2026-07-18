import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from agents7.eval import (
    AGENT_TYPE_MAP,
    build_agent,
    load_eval_rows,
    model_output_fields,
    normalise_rows,
)
from agents7.exceptions import Agents7Exception
from routers.catalog import find_config_file
from routers.utils import _load_config, reject_tool_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eval", tags=["eval"])


def _find_golden_set(config_file: Path) -> Path | None:
    data_dir = config_file.parent / "data"
    for name in ("golden_set.csv", "golden_set.jsonl"):
        path = data_dir / name
        if path.exists():
            return path
    return None


@router.post("/{agent_name}")
def eval_agent(agent_name: str) -> dict:
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

    agent_type = (cfg.get("agent_type") or "").lower()
    if agent_type not in AGENT_TYPE_MAP:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown agent_type '{agent_type}' — "
                f"must be one of: {list(AGENT_TYPE_MAP)}"
            ),
        )
    reject_tool_agent(agent_type)

    rows = load_eval_rows(golden_path)
    if not rows:
        raise HTTPException(status_code=422, detail="Golden set is empty")

    try:
        eval_rows, expected_fields = normalise_rows(
            rows, model_output_fields(cfg)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    agent = build_agent(config_file, agent_type)

    # Primary field for per-category breakdown (`category` sorts first).
    category_field = expected_fields[0] if expected_fields else None

    results = []
    for eval_row in eval_rows:
        input_data = eval_row["input"]
        expected = {f: eval_row[f] for f in expected_fields if f in eval_row}

        try:
            response = agent.act(input_data)
            actual = response.model.model_dump() if response.model else None
        except Agents7Exception as exc:
            # Log only the input *keys*, never the values (PII). A scalar
            # input has no keys, so use a placeholder rather than leaking
            # the value.
            input_keys = (
                list(input_data.keys())
                if isinstance(input_data, dict)
                else ["<input>"]
            )
            logger.warning(
                "agent.act() failed (input keys: %s): %s",
                input_keys,
                exc,
                exc_info=True,
            )
            actual = None

        passed = actual is not None and all(
            str(actual.get(k, "")).upper() == str(v).upper()
            for k, v in expected.items()
        )

        results.append(
            {
                "input": input_data,
                "expected": expected,
                "actual": actual,
                "passed": passed,
            }
        )

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])

    per_category: dict[str, dict] = {}
    if category_field:
        for r in results:
            cat = r["expected"].get(category_field, "UNKNOWN")
            bucket = per_category.setdefault(cat, {"total": 0, "passed": 0})
            bucket["total"] += 1
            if r["passed"]:
                bucket["passed"] += 1
        for stats in per_category.values():
            stats["accuracy"] = (
                stats["passed"] / stats["total"]
                if stats["total"] > 0
                else 0.0
            )

    return {
        "agent": cfg.get("name"),
        "golden_set": golden_path.name,
        "total": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "accuracy": passed_count / total if total > 0 else 0.0,
        "per_category": per_category,
        "mismatches": [r for r in results if not r["passed"]],
    }
