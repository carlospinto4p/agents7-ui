"""Stateful chat sessions for Chatter-family agents."""

import logging
import time
import uuid

import yaml
from fastapi import APIRouter, HTTPException, Request

from routers.catalog import find_config_file

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

_CHATTER_TYPE_MAP = {
    "chatter": "agents7.agents.Chatter",
    "personality_chatter": "agents7.agents.PersonalityChatter",
    "scene_chatter": "agents7.agents.SceneChatter",
    "guarded_chatter": "agents7.agents.GuardedChatter",
    "guarded_scene_chatter": "agents7.agents.GuardedSceneChatter",
}

_SESSION_TTL = 3600  # seconds
_sessions: dict[str, object] = {}
_session_times: dict[str, float] = {}

_MAX_STARTS_PER_WINDOW = 20
_RATE_WINDOW = 60  # seconds
_start_counts: dict[str, tuple[int, float]] = {}


def _import_class(dotted_path: str):
    import importlib

    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _check_start_rate(client_ip: str) -> None:
    now = time.monotonic()
    count, window_start = _start_counts.get(client_ip, (0, now))
    if now - window_start > _RATE_WINDOW:
        count, window_start = 0, now
    count += 1
    _start_counts[client_ip] = (count, window_start)
    if count > _MAX_STARTS_PER_WINDOW:
        raise HTTPException(
            status_code=429, detail="Too many session requests"
        )


def _evict_expired_sessions() -> None:
    now = time.monotonic()
    expired = [
        sid for sid, t in _session_times.items() if now - t > _SESSION_TTL
    ]
    for sid in expired:
        _sessions.pop(sid, None)
        _session_times.pop(sid, None)


@router.post("/start/{agent_name}")
def start_chat(agent_name: str, request: Request) -> dict:
    client_ip = request.client.host if request.client else "unknown"
    _check_start_rate(client_ip)
    _evict_expired_sessions()
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
    _session_times[session_id] = time.monotonic()
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
        logger.exception("Chat error in session %s", session_id)
        raise HTTPException(
            status_code=500, detail="Internal chat error"
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
    _session_times.pop(session_id, None)
    return {"ok": True}
