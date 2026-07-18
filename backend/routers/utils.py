from pathlib import Path

import yaml
from fastapi import HTTPException


# Structured-agent type→class resolution lives in the framework
# (`agents7.eval.AGENT_TYPE_MAP` / `build_agent`); dotted-path
# imports use `agents7.agents.utils.import_from_path`. This module
# keeps only the chatter map, which has no framework equivalent.
CHATTER_TYPE_MAP = {
    "chatter": "agents7.agents.Chatter",
    # PersonalityChatter/SceneChatter were removed in agents7
    # v4.0.0; persona/scene are now Chatter composition plugins,
    # so these legacy agent_types map to Chatter (which loads the
    # persona/scene YAML sections).
    "personality_chatter": "agents7.agents.Chatter",
    "scene_chatter": "agents7.agents.Chatter",
    "guarded_chatter": "agents7.agents.GuardedChatter",
    "guarded_scene_chatter": "agents7.agents.GuardedSceneChatter",
}


def _resolve_agent_path(
    agent_path: str,
    config_dir: Path,
    catalog_root: Path,
    allow_absolute: bool = True,
) -> str:
    """Resolve a pipeline step's agent path, guarding catalog escape.

    Shared by the run endpoint (which executes the agent) and the
    catalog browse endpoint (which only reads it for display). A
    relative path is resolved against *config_dir* and must stay
    within *catalog_root*; otherwise a `ValueError` is raised.

    :param agent_path: The ``agent`` field from a pipeline step.
    :param config_dir: Directory of the pipeline config file.
    :param catalog_root: Catalog root the path must stay within.
    :param allow_absolute: If True (the run endpoint's behaviour),
        an absolute path is returned unchanged. If False (browse),
        an absolute path is rejected like any escaping path so a
        crafted config cannot read arbitrary files.
    :return: The resolved path as a string.
    :raises ValueError: If the path escapes ``catalog_root`` (or is
        absolute when ``allow_absolute`` is False).
    """
    p = Path(agent_path)
    if p.is_absolute():
        if allow_absolute:
            return agent_path
        raise ValueError(f"Step agent path must be relative: {agent_path!r}")
    resolved = (config_dir / p).resolve()
    try:
        resolved.relative_to(catalog_root.resolve())
    except ValueError:
        raise ValueError(
            f"Step agent path escapes catalog root: {agent_path!r}"
        )
    return str(resolved)


def reject_tool_agent(agent_type: str) -> None:
    """Reject a tool agent on the structured-output endpoints.

    ``tool`` joined `agents7.eval.AGENT_TYPE_MAP` when the framework
    gained trajectory scoring, so it now passes the membership check
    both the run and eval endpoints use. Neither can serve it: they
    read ``response.model``, which a `ToolAgent` never populates —
    it answers in free text and is scored on the calls it makes.
    Fail loudly here rather than return an empty output as if the
    agent had produced nothing.

    :param agent_type: The config's ``agent_type``, lowercased.
    :raises HTTPException: 422 if *agent_type* is ``tool``.
    """
    if agent_type == "tool":
        raise HTTPException(
            status_code=422,
            detail=(
                "Tool agents are not supported by this endpoint — "
                "they answer in free text and are scored on their "
                "tool-call trajectory. Use `agents7 eval` or "
                "`agents7.eval.run_eval_suite`."
            ),
        )


def _load_config(config_file: Path) -> tuple[dict, str]:
    """Load a YAML config file and return (parsed dict, raw text)."""
    with open(config_file, encoding="utf-8") as f:
        raw_yaml = f.read()
    cfg: dict = yaml.safe_load(raw_yaml)
    return cfg, raw_yaml


def _load_output_schema(
    cfg: dict,
) -> tuple[dict | None, set[str]]:
    """Resolve output model from cfg and return (schema, field names)."""
    output_model_path = cfg.get("output_model")
    if not output_model_path:
        return None, set()
    try:
        from agents7.agents.utils import import_from_path

        model_cls = import_from_path(output_model_path)
        schema: dict = model_cls.model_json_schema()
        return schema, set(schema.get("properties", {}).keys())
    except (ImportError, AttributeError):
        return None, set()
