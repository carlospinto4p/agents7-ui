import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from routers.utils import _load_config, _load_output_schema

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

_default = str(Path(__file__).parents[3] / "agents_catalog")
CATALOG_PATH = Path(os.getenv("CATALOG_PATH", _default))

_catalog_cache: list[Path] | None = None
_name_index: dict[str, Path] | None = None


def _ensure_catalog_loaded() -> None:
    global _catalog_cache, _name_index
    if _catalog_cache is not None:
        return
    _catalog_cache = []
    _name_index = {}
    if CATALOG_PATH.exists():
        for p in sorted(CATALOG_PATH.rglob("config.yml")):
            _catalog_cache.append(p)
            cfg, _ = _load_config(p)
            name = (cfg.get("name") or "").lower()
            if name:
                _name_index[name] = p


def _agent_source(config_file: Path) -> str:
    if "examples" in config_file.parts:
        if (config_file.parent / "data" / "golden_set.jsonl").exists():
            return "integration_test"
        return "example"
    return "catalog"


def _display_name(cfg: dict) -> str | None:
    persona = cfg.get("persona") or {}
    return persona.get("full_name") or cfg.get("name")


def _resolve_pipeline_step_details(
    config_file: Path, steps: list[dict]
) -> list[dict]:
    details = []
    for step in steps:
        agent_ref = step.get("agent")
        if not agent_ref:
            continue
        step_path = (config_file.parent / agent_ref).resolve()
        entry: dict = {"name": agent_ref, "provider": None, "model": None}
        if step_path.exists():
            try:
                cfg, _ = _load_config(step_path)
                engine = cfg.get("engine") or {}
                entry["name"] = (
                    _display_name(cfg) or cfg.get("name") or agent_ref
                )
                entry["provider"] = engine.get("provider")
                entry["model"] = engine.get("model")
            except Exception:
                pass
        details.append(entry)
    return details


def _pipeline_data(
    config_file: Path, cfg: dict
) -> tuple[list[str] | None, list[dict] | None]:
    if cfg.get("agent_type") != "pipeline":
        return None, None
    steps = cfg.get("steps") or []
    if not steps:
        return None, None
    details = _resolve_pipeline_step_details(config_file, steps)
    names = [d["name"] for d in details]
    return names, details


def _parse_summary(config_file: Path) -> dict:
    cfg, _ = _load_config(config_file)
    engine = cfg.get("engine") or {}
    pipeline_steps, step_engines = _pipeline_data(config_file, cfg)
    return {
        "name": cfg.get("name"),
        "display_name": _display_name(cfg),
        "version": cfg.get("version"),
        "agent_type": cfg.get("agent_type"),
        "provider": engine.get("provider"),
        "model": engine.get("model"),
        "pipeline_steps": pipeline_steps,
        "step_engines": step_engines,
        "source": _agent_source(config_file),
    }


def _parse_detail(config_file: Path) -> dict:
    cfg, raw_yaml = _load_config(config_file)
    engine = cfg.get("engine") or {}
    output_schema, _ = _load_output_schema(cfg)
    pipeline_steps, step_engines = _pipeline_data(config_file, cfg)

    return {
        "name": cfg.get("name"),
        "display_name": _display_name(cfg),
        "version": cfg.get("version"),
        "agent_type": cfg.get("agent_type"),
        "provider": engine.get("provider"),
        "model": engine.get("model"),
        "pipeline_steps": pipeline_steps,
        "step_engines": step_engines,
        "system_prompt": cfg.get("system_prompt"),
        "output_model": cfg.get("output_model"),
        "output_schema": output_schema,
        "system_examples": cfg.get("system_examples"),
        "raw_yaml": raw_yaml,
        "source": _agent_source(config_file),
    }


def find_config_file(agent_name: str) -> Path | None:
    """Return config.yml path for agent_name (case-insensitive)."""
    _ensure_catalog_loaded()
    return _name_index.get(agent_name.lower())  # type: ignore[union-attr]


@router.get("")
def list_agents() -> list[dict]:
    _ensure_catalog_loaded()
    return [_parse_summary(c) for c in _catalog_cache]  # type: ignore[arg-type]


@router.get("/{agent_name}")
def get_agent(agent_name: str) -> dict:
    config_file = find_config_file(agent_name)
    if config_file is None:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        )
    return _parse_detail(config_file)
