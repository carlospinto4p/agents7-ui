from fastapi import APIRouter, HTTPException, Request
from pathlib import Path

from agents7.exceptions import (
    AgentConfigurationError,
    PipelineConfigurationError,
)
from routers.catalog import CATALOG_PATH, find_config_file
from routers.utils import (
    AGENT_TYPE_MAP,
    _load_config,
    _resolve_agent_path,
    import_class,
)

router = APIRouter(prefix="/api/run", tags=["run"])


def _build_pipeline(config_file: Path, cfg: dict):
    """Build a Pipeline resolving step agent paths relative to config_file."""
    from agents7.agents import Labeler
    from agents7.agents.pipeline import Pipeline, PipelineStep
    from agents7.agents.utils import import_from_path

    catalog_root = CATALOG_PATH.resolve()
    config_dir = config_file.parent
    steps = []
    for step_cfg in cfg.get("steps", []):
        agent_path = _resolve_agent_path(
            step_cfg.get("agent", ""), config_dir, catalog_root
        )

        step_type_path = step_cfg.get("agent_type")
        if step_type_path:
            step_cls = import_class(step_type_path)
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

    cfg, _ = _load_config(config_file)
    agent_type = (cfg.get("agent_type") or "").lower()
    body = await request.json()
    input_data = body.get("input_data", body)

    if agent_type == "pipeline":
        try:
            agent = _build_pipeline(config_file, cfg)
        except (
            AgentConfigurationError,
            PipelineConfigurationError,
            ValueError,
            ImportError,
        ) as exc:
            raise HTTPException(
                status_code=422, detail=f"Pipeline build failed: {exc}"
            ) from exc

        response = agent.act(input_data)
        output = (
            response.model.model_dump()
            if response.model is not None
            else None
        )
        step_metrics = [s.metrics for s in response.steps]

        steps_data = []
        current_input = input_data
        for pipeline_step, step_resp in zip(agent.steps, response.steps):
            step_out = (
                step_resp.model.model_dump()
                if step_resp.model is not None
                else None
            )
            steps_data.append(
                {
                    "name": getattr(pipeline_step.agent, "name", ""),
                    "input": current_input,
                    "output": step_out,
                    "metrics": {
                        "tokens": step_resp.metrics.tokens,
                        "prompt_tokens": step_resp.metrics.prompt_tokens,
                        "total_duration": step_resp.metrics.total_duration,
                        "cost_cents": step_resp.metrics.cost_cents,
                    },
                }
            )
            if step_out is not None:
                current_input = step_out

        return {
            "agent": cfg.get("name"),
            "output": output,
            "raw_response": None,
            "parse_error": not response.success,
            "steps": steps_data,
            "metrics": {
                "tokens": sum(m.tokens for m in step_metrics),
                "prompt_tokens": sum(m.prompt_tokens for m in step_metrics),
                "total_duration": sum(m.total_duration for m in step_metrics),
                "cost_cents": (
                    sum(m.cost_cents for m in step_metrics if m.cost_cents)
                    or None
                ),
            },
        }

    class_path = AGENT_TYPE_MAP.get(agent_type)
    if not class_path:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown agent_type '{agent_type}' in config — "
                f"must be one of: {list(AGENT_TYPE_MAP) + ['pipeline']}"
            ),
        )

    AgentClass = import_class(class_path)
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
