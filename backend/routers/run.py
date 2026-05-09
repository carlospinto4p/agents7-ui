import yaml
from fastapi import APIRouter, HTTPException, Request

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
    class_path = _AGENT_TYPE_MAP.get(agent_type)
    if not class_path:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown agent_type '{agent_type}' in config — "
                f"must be one of: {list(_AGENT_TYPE_MAP)}"
            ),
        )

    AgentClass = _import_agent_class(class_path)
    agent = AgentClass.from_yaml(str(config_file))

    body = await request.json()
    input_data = body.get("input_data", body)

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
