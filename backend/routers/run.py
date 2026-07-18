from fastapi import APIRouter, HTTPException, Request
from pathlib import Path

from agents7.agents.tool_agent import ToolStepEvent
from agents7.eval import AGENT_TYPE_MAP, build_agent
from agents7.exceptions import (
    AgentConfigurationError,
    PipelineConfigurationError,
    ToolLoopError,
)
from routers.catalog import CATALOG_PATH, find_config_file
from routers.utils import _load_config, _resolve_agent_path

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
            step_cls = import_from_path(step_type_path)
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


def _step_payload(event: ToolStepEvent) -> dict:
    """Serialize one `ToolStepEvent` for the run response.

    Only the fields the step kind actually populates are emitted,
    so a ``tool_call`` step carries its arguments and a
    ``tool_result`` its result rather than a row of nulls.

    :param event: The event yielded by the agent's stream.
    :return: A JSON-serializable step dict.
    """
    step: dict = {"kind": str(event.kind), "iteration": event.iteration}
    if event.name is not None:
        step["name"] = event.name
    if event.arguments is not None:
        step["arguments"] = event.arguments
    if event.result is not None:
        step["result"] = event.result
    return step


def _tool_metrics(response) -> dict:
    """Return the metrics block for a tool run.

    A loop that exceeded ``max_iterations`` never produced an
    `AgentResponse`, so report zeroes rather than failing the whole
    request — the steps collected so far are the useful part.

    :param response: The final `AgentResponse`, or None.
    :return: The metrics dict for the run response.
    """
    if response is None:
        return {
            "tokens": 0,
            "prompt_tokens": 0,
            "total_duration": 0.0,
            "cost_cents": None,
        }
    return {
        "tokens": response.metrics.tokens,
        "prompt_tokens": response.metrics.prompt_tokens,
        "total_duration": response.metrics.total_duration,
        "cost_cents": response.metrics.cost_cents,
    }


def _run_tool_agent(config_file: Path, cfg: dict, input_data) -> dict:
    """Run a tool agent, returning its answer and its trajectory.

    A `ToolAgent` answers in free text and never populates
    ``response.model``, so the structured ``output`` stays None and
    the answer is served as ``answer``. The loop is driven through
    ``act_stream`` so the intermediate tool calls and their results
    are reported alongside it.

    :param config_file: Path to the agent's YAML config.
    :param cfg: The parsed config.
    :param input_data: The request's input — a tool agent answers a
        user message, so this must be a string.
    :return: The run response payload.
    :raises HTTPException: 422 if *input_data* is not a string.
    """
    if not isinstance(input_data, str):
        raise HTTPException(
            status_code=422,
            detail=(
                "A tool agent answers a user message, so its input "
                f"must be a string, got {type(input_data).__name__}."
            ),
        )

    agent = build_agent(config_file, "tool")
    stream = agent.act_stream(input_data)

    steps: list[dict] = []
    error: str | None = None
    try:
        for event in stream:
            steps.append(_step_payload(event))
    except ToolLoopError as exc:
        # The loop ran out of iterations without answering. Report
        # the calls it did make rather than losing them to a 500 —
        # they are exactly what explains why it never converged.
        error = str(exc)

    response = stream.agent_response
    return {
        "agent": cfg.get("name"),
        "answer": response.response if response is not None else None,
        "thinking": response.thinking if response is not None else None,
        "tool_steps": steps,
        "error": error,
        "output": None,
        "raw_response": response.response if response is not None else None,
        "parse_error": error is not None,
        "metrics": _tool_metrics(response),
    }


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
    input_data = (
        body.get("input_data", body) if isinstance(body, dict) else body
    )

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

    if agent_type not in AGENT_TYPE_MAP:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unknown agent_type '{agent_type}' in config — "
                f"must be one of: {list(AGENT_TYPE_MAP) + ['pipeline']}"
            ),
        )
    if agent_type == "tool":
        return _run_tool_agent(config_file, cfg, input_data)

    agent = build_agent(config_file, agent_type)

    if isinstance(input_data, dict):
        response = agent.act(input_data)
    else:
        # Scalar input (a single free-text string): the framework's
        # single act() only accepts dicts, so mirror how eval runs
        # scalar rows — through the batch path, which formats the raw
        # value into the prompt without inventing a synthetic key.
        batch = agent.act_in_batch([input_data], iter_func=None)
        if not batch:
            return {
                "agent": cfg.get("name"),
                "output": None,
                "raw_response": None,
                "parse_error": True,
                "metrics": {
                    "tokens": 0,
                    "prompt_tokens": 0,
                    "total_duration": 0.0,
                    "cost_cents": None,
                },
            }
        response = batch[0]

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
