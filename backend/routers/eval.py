import csv
import json
import logging
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from routers.catalog import find_config_file
from routers.run import _AGENT_TYPE_MAP, _import_agent_class

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/eval", tags=["eval"])

_METADATA_COLUMNS = {"timestamp", "note", "source", "id", "split"}


def _find_golden_set(config_file: Path) -> Path | None:
    data_dir = config_file.parent / "data"
    for name in ("golden_set.csv", "golden_set.jsonl"):
        path = data_dir / name
        if path.exists():
            return path
    return None


def _load_golden_set(path: Path) -> list[dict]:
    if path.suffix == ".csv":
        with open(path, encoding="utf-8", newline="") as f:
            return [dict(row) for row in csv.DictReader(f)]
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


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

    with open(config_file, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    agent_type = (cfg.get("agent_type") or "").lower()
    class_path = _AGENT_TYPE_MAP.get(agent_type)
    if not class_path:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown agent_type '{agent_type}'",
        )

    output_fields: set[str] = set()
    output_model_path = cfg.get("output_model")
    if output_model_path:
        try:
            from agents7.agents.utils import import_from_path

            model_cls = import_from_path(output_model_path)
            schema = model_cls.model_json_schema()
            output_fields = set(schema.get("properties", {}).keys())
        except (ImportError, AttributeError):
            pass

    rows = _load_golden_set(golden_path)
    if not rows:
        raise HTTPException(status_code=422, detail="Golden set is empty")

    input_cols = set(rows[0].keys()) - output_fields - _METADATA_COLUMNS
    AgentClass = _import_agent_class(class_path)
    agent = AgentClass.from_yaml(str(config_file))

    # Primary field for per-category breakdown
    category_field = (
        "category"
        if "category" in output_fields
        else (next(iter(output_fields)) if output_fields else None)
    )

    results = []
    for row in rows:
        if len(input_cols) == 1:
            input_data = row[next(iter(input_cols))]
        else:
            input_data = {c: row[c] for c in input_cols if row.get(c)}

        expected = {k: v for k, v in row.items() if k in output_fields and v}

        try:
            response = agent.act(input_data)
            actual = response.model.model_dump() if response.model else None
        except Exception as exc:
            logger.warning(
                "agent.act() failed for input %r: %s",
                input_data,
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
