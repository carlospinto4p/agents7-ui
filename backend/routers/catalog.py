import os
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

_default = str(Path(__file__).parents[3] / "agents_catalog")
CATALOG_PATH = Path(os.getenv("CATALOG_PATH", _default))


def _parse_summary(config_file: Path) -> dict:
    with open(config_file, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    engine = cfg.get("engine") or {}
    return {
        "name": cfg.get("name"),
        "version": cfg.get("version"),
        "agent_type": cfg.get("agent_type"),
        "provider": engine.get("provider"),
        "model": engine.get("model"),
    }


def _parse_detail(config_file: Path) -> dict:
    with open(config_file, encoding="utf-8") as f:
        raw_yaml = f.read()
    cfg = yaml.safe_load(raw_yaml)
    engine = cfg.get("engine") or {}

    output_model_path = cfg.get("output_model")
    output_schema = None
    if output_model_path:
        try:
            from agents7.agents.utils import import_from_path

            model_cls = import_from_path(output_model_path)
            output_schema = model_cls.model_json_schema()
        except Exception:
            pass

    return {
        "name": cfg.get("name"),
        "version": cfg.get("version"),
        "agent_type": cfg.get("agent_type"),
        "provider": engine.get("provider"),
        "model": engine.get("model"),
        "system_prompt": cfg.get("system_prompt"),
        "output_model": output_model_path,
        "output_schema": output_schema,
        "system_examples": cfg.get("system_examples"),
        "raw_yaml": raw_yaml,
    }


def find_config_file(agent_name: str) -> Path | None:
    """Return config.yml path for agent_name (case-insensitive)."""
    for config_file in sorted(CATALOG_PATH.rglob("config.yml")):
        with open(config_file, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        if (cfg.get("name") or "").lower() == agent_name.lower():
            return config_file
    return None


@router.get("")
def list_agents() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    return [
        _parse_summary(c) for c in sorted(CATALOG_PATH.rglob("config.yml"))
    ]


@router.get("/{agent_name}")
def get_agent(agent_name: str) -> dict:
    config_file = find_config_file(agent_name)
    if config_file is None:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        )
    return _parse_detail(config_file)
