"""Stateful chat sessions for Chatter-family agents."""

import uuid

import yaml
from fastapi import APIRouter, HTTPException, Request

from routers.catalog import find_config_file

router = APIRouter(prefix="/api/chat", tags=["chat"])

_CHATTER_TYPE_MAP = {
    "chatter": "agents7.agents.Chatter",
    "personality_chatter": "agents7.agents.PersonalityChatter",
    "scene_chatter": "agents7.agents.SceneChatter",
    "guarded_chatter": "agents7.agents.GuardedChatter",
    "guarded_scene_chatter": "agents7.agents.GuardedSceneChatter",
}

_sessions: dict[str, object] = {}


def _import_class(dotted_path: str):
    import importlib

    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


@router.post("/start/{agent_name}")
def start_chat(agent_name: str) -> dict:
    config_file = find_config_file(agent_name)
    if config_file is None:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        )

    with open(config_file, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    agent_type = (cfg.get("agent_type") or "").lower()
    class_path = _CHATTER_TYPE_MAP.get(agent_type)
    if not class_path:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Agent '{agent_name}' has type '{agent_type}', "
                f"not a chatter. Must be one of: {list(_CHATTER_TYPE_MAP)}"
            ),
        )

    ChatterClass = _import_class(class_path)
    chatter = ChatterClass.from_yaml(str(config_file))

    session_id = str(uuid.uuid4())
    _sessions[session_id] = chatter
    return {"session_id": session_id, "agent": cfg.get("name")}


@router.post("/{session_id}/message")
async def send_message(session_id: str, request: Request) -> dict:
    chatter = _sessions.get(session_id)
    if chatter is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' not found"
        )

    body = await request.json()
    message = body.get("message", "")
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    try:
        response = chatter.chat(message)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Chat error: {exc}"
        ) from exc

    return {
        "response": response.response,
        "metrics": {
            "tokens": response.metrics.tokens,
            "prompt_tokens": response.metrics.prompt_tokens,
            "total_duration": response.metrics.total_duration,
        },
    }


@router.delete("/{session_id}")
def end_session(session_id: str) -> dict:
    _sessions.pop(session_id, None)
    return {"ok": True}
