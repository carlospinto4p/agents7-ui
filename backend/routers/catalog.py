import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from routers.utils import (
    _load_config,
    _load_output_schema,
    _resolve_agent_path,
)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])
logger = logging.getLogger(__name__)

_default = str(Path(__file__).parents[3] / "agents_catalog")
CATALOG_PATH = Path(os.getenv("CATALOG_PATH", _default))

_catalog_cache: list[Path] | None = None
_name_index: dict[str, Path] | None = None

# Directories that hold build/install artifacts, not real agent configs.
# Catalog agents that ship as packages get a copy of their config.yml
# under build/ (e.g. build/lib/<pkg>/config.yml) and inside any local
# virtualenv's site-packages; scanning those would list the agent twice.
_SKIP_DIRS = {
    "build",
    "dist",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "site-packages",
}


def _is_catalog_config(p: Path) -> bool:
    """Return ``True`` if ``p`` is a real agent config, not an artifact."""
    return not any(
        part in _SKIP_DIRS or part.endswith(".egg-info") for part in p.parts
    )


def _ensure_catalog_loaded() -> None:
    global _catalog_cache, _name_index
    if _catalog_cache is not None:
        return
    _catalog_cache = []
    _name_index = {}
    if CATALOG_PATH.exists():
        for p in sorted(CATALOG_PATH.rglob("config.yml")):
            if not _is_catalog_config(p):
                continue
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


def _first_sentences(text: str, limit: int = 220) -> str:
    """Condense *text* into a short single-line blurb.

    Collapses whitespace and truncates on a word boundary so a
    derived description stays compact in the UI.

    :param text: Source text (e.g. a system prompt or backstory).
    :param limit: Maximum length before truncation.
    :return: A compact one-line summary.
    """
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[:limit].rsplit(" ", 1)[0].rstrip() + "…"


def _description(cfg: dict) -> str | None:
    """Return a human description of what the agent does.

    Prefers an explicit ``description`` field in the config. When
    absent, falls back to a short summary derived from the persona
    backstory or system prompt, so agents without a curated
    description still surface something meaningful.

    :param cfg: Parsed agent config dictionary.
    :return: A description string, or ``None`` if nothing is
        available to derive one from.
    """
    explicit = cfg.get("description")
    if explicit:
        return str(explicit).strip()
    persona = cfg.get("persona") or {}
    if backstory := persona.get("backstory"):
        return _first_sentences(str(backstory))
    prompt = cfg.get("system_prompt")
    if prompt and str(prompt).strip() not in ("", "(auto-generated)"):
        return _first_sentences(str(prompt))
    return None


def _demonstrates(cfg: dict) -> str | None:
    """Return what framework capability this agent demonstrates.

    Only meaningful for samples under `examples/` — a catalog agent
    solves a real task rather than showcasing a capability, so it
    typically has no `demonstrates` field.

    :param cfg: Parsed agent config dictionary.
    :return: The `demonstrates` string, or `None` if absent.
    """
    demonstrates = cfg.get("demonstrates")
    if not demonstrates:
        return None
    return str(demonstrates).strip() or None


def _resolve_pipeline_step_details(
    config_file: Path, steps: list[dict]
) -> list[dict]:
    catalog_root = CATALOG_PATH.resolve()
    details = []
    for step in steps:
        agent_ref = step.get("agent")
        if not agent_ref:
            continue
        entry: dict = {"name": agent_ref, "provider": None, "model": None}
        # Guard against path traversal: a crafted pipeline config
        # must not make us read (and leak) files outside the catalog.
        try:
            step_path = Path(
                _resolve_agent_path(
                    agent_ref,
                    config_file.parent,
                    catalog_root,
                    allow_absolute=False,
                )
            )
        except ValueError:
            details.append(entry)
            continue
        if step_path.exists():
            try:
                cfg, _ = _load_config(step_path)
                engine = cfg.get("engine") or {}
                entry["name"] = (
                    _display_name(cfg) or cfg.get("name") or agent_ref
                )
                entry["provider"] = engine.get("provider")
                entry["model"] = engine.get("model")
            except Exception as e:
                # Keep listing resilient: one unreadable step config
                # must not break the whole catalog response. Surface it
                # in the warning log rather than swallowing silently.
                logger.warning(
                    "Could not read pipeline step config %s: %s",
                    step_path,
                    e,
                )
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
        "description": _description(cfg),
        "demonstrates": _demonstrates(cfg),
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
        "description": _description(cfg),
        "demonstrates": _demonstrates(cfg),
        "version": cfg.get("version"),
        "agent_type": cfg.get("agent_type"),
        "provider": engine.get("provider"),
        "model": engine.get("model"),
        "pipeline_steps": pipeline_steps,
        "step_engines": step_engines,
        "system_prompt": cfg.get("system_prompt"),
        "persona": cfg.get("persona"),
        "scene": cfg.get("scene"),
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
