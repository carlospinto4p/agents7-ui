import yaml
from fastapi import APIRouter, HTTPException, Request
from pathlib import Path

from routers.catalog import find_config_file

router = APIRouter(prefix="/api/run", tags=["run"])

_AGENT_TYPE_MAP = {
    "classifier": "agents7.agents.Classifier",
    "labeler": "agents7.agents.Labeler",
    "detector": "agents7.agents.Detector",
    "regressor": "agents7.agents.Regressor",
}


def _import_agent_class(dotted_path: str):
    import importlib

    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _build_pipeline(config_file: Path, cfg: dict):
    """Build a Pipeline resolving step agent paths relative to config_file."""
    from agents7.agents import Labeler
    from agents7.agents.pipeline import Pipeline, PipelineStep
    from agents7.agents.utils import import_from_path

    config_dir = config_file.parent
    steps = []
    for step_cfg in cfg.get("steps", []):
        agent_path = step_cfg.get("agent", "")
        p = Path(agent_path)
        if not p.is_absolute():
            agent_path = str(config_dir / p)

        step_type_path = step_cfg.get("agent_type")
        if step_type_path:
            step_cls = _import_agent_class(step_type_path)
        else:
            step_cls = Labeler

        step_agent = step_cls.from_yaml(agent_path)

        mapper = None
        if step_cfg.get("mapper"):
            mapper = import_from_path(step_cfg["mapper"])

        condition = None
        if step_cfg.get("condition"):
            condition = import_from_path(step_cfg["condition"])

        steps.append(
            PipelineStep(
                agent=step_agent,
                mapper=mapper,
                condition=condition,
            )
        )

    return Pipeline(steps=steps)


@router.post("/{agent_name}")
async def run_agent(agent_name: str, request: Request) -> dict:
    config_file = find_config_file(agent_name)
    if config_file is None:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        )

    with open(config_file, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    agent_type = (cfg.get("agent_type") or "").lower()
    body = await request.json()
    input_data = body.get("input_data", body)

    if agent_type == "pipeline":
        try:
            agent = _build_pipeline(config_file, cfg)
        except Exception as exc:
            raise HTTPException(
                status_code=422, detail=f"Pipeline build failed: {exc}"
            ) from exc

        response = agent.act(input_data)
        output = (
            response.model.model_dump()
            if response.model is not None
            else None
        )
        return {
            "agent": cfg.get("name"),
            "output": output,
            "raw_response": None,
            "parse_error": not response.success,
            "metrics": {
                "tokens": None,
                "prompt_tokens": None,
                "total_duration": None,
                "cost_cents": None,
            },
        }

    class_path = _AGENT_TYPE_MAP.get(agent_type)
    if not class_path:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown agent_type '{agent_type}' in config — "
                f"must be one of: {list(_AGENT_TYPE_MAP) + ['pipeline']}"
            ),
        )

    AgentClass = _import_agent_class(class_path)
    agent = AgentClass.from_yaml(str(config_file))
    response = agent.act(input_data)

    output = None
    if response.model is not None:
        output = response.model.model_dump()

    return {
        "agent": cfg.get("name"),
        "output": output,
        "raw_response": response.response,
        "parse_error": response.model is None,
        "metrics": {
            "tokens": response.metrics.tokens,
            "prompt_tokens": response.metrics.prompt_tokens,
            "total_duration": response.metrics.total_duration,
            "cost_cents": response.metrics.cost_cents,
        },
    }
