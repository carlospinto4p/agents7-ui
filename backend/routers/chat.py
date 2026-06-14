"""Stateful chat sessions for Chatter-family agents."""

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agents7.exceptions import Agents7Exception
from routers.catalog import find_config_file
from routers.utils import CHATTER_TYPE_MAP, _load_config, import_class

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class _SessionStore:
    _SESSION_TTL = 3600
    _MAX_STARTS = 20
    _RATE_WINDOW = 60
    _CLEANUP_INTERVAL = 300

    def __init__(self) -> None:
        self._sessions: dict[str, object] = {}
        self._session_times: dict[str, float] = {}
        self._start_counts: dict[str, tuple[int, float]] = {}

    def check_start_rate(self, client_ip: str) -> None:
        now = time.monotonic()
        count, window_start = self._start_counts.get(client_ip, (0, now))
        if now - window_start > self._RATE_WINDOW:
            count, window_start = 0, now
        count += 1
        self._start_counts[client_ip] = (count, window_start)
        if count > self._MAX_STARTS:
            raise HTTPException(
                status_code=429, detail="Too many session requests"
            )

    def evict_expired(self) -> None:
        now = time.monotonic()
        expired = [
            sid
            for sid, t in self._session_times.items()
            if now - t > self._SESSION_TTL
        ]
        for sid in expired:
            self._sessions.pop(sid, None)
            self._session_times.pop(sid, None)

    async def run_periodic_cleanup(self) -> None:
        """Evict expired sessions on a fixed interval until cancelled.

        Complements the on-demand eviction in ``start_chat`` so idle
        sessions are reclaimed even when no new chats are started.
        """
        while True:
            await asyncio.sleep(self._CLEANUP_INTERVAL)
            self.evict_expired()

    def create(self, chatter: object) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = chatter
        self._session_times[session_id] = time.monotonic()
        return session_id

    def get(self, session_id: str) -> object | None:
        return self._sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._session_times.pop(session_id, None)


_store = _SessionStore()


@router.post("/start/{agent_name}")
def start_chat(agent_name: str, request: Request) -> dict:
    client_ip = request.client.host if request.client else "unknown"
    _store.check_start_rate(client_ip)
    _store.evict_expired()
    config_file = find_config_file(agent_name)
    if config_file is None:
        raise HTTPException(
            status_code=404, detail=f"Agent '{agent_name}' not found"
        )

    cfg, _ = _load_config(config_file)
    agent_type = (cfg.get("agent_type") or "").lower()
    class_path = CHATTER_TYPE_MAP.get(agent_type)
    if not class_path:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Agent '{agent_name}' has type '{agent_type}', "
                f"not a chatter. Must be one of: {list(CHATTER_TYPE_MAP)}"
            ),
        )

    ChatterClass = import_class(class_path)
    chatter = ChatterClass.from_yaml(str(config_file))
    session_id = _store.create(chatter)
    return {"session_id": session_id, "agent": cfg.get("name")}


@router.post("/{session_id}/message")
async def send_message(session_id: str, request: Request) -> dict:
    chatter = _store.get(session_id)
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
    except Agents7Exception as exc:
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


def _sse(data: dict, event: str | None = None) -> str:
    """Format a Server-Sent Events frame from a JSON payload."""
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/{session_id}/stream")
async def stream_message(
    session_id: str, request: Request
) -> StreamingResponse:
    """Stream a chat reply token-by-token via Server-Sent Events.

    Emits one ``data: {"delta": "..."}`` frame per text chunk,
    then a final ``event: done`` frame carrying the turn metrics.
    A framework error mid-stream is reported as ``event: error``
    rather than an HTTP status, since the response has already
    started.
    """
    chatter = _store.get(session_id)
    if chatter is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' not found"
        )

    body = await request.json()
    message = body.get("message", "")
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    async def event_stream():
        try:
            stream = await chatter.chat_stream_async(message)
            async for chunk in stream:
                yield _sse({"delta": chunk})
            resp = stream.chat_response
            metrics = (
                {
                    "tokens": resp.metrics.tokens,
                    "prompt_tokens": resp.metrics.prompt_tokens,
                    "total_duration": resp.metrics.total_duration,
                }
                if resp is not None
                else {}
            )
            yield _sse({"metrics": metrics}, event="done")
        except Agents7Exception:
            logger.exception("Chat stream error in session %s", session_id)
            yield _sse({"error": "Internal chat error"}, event="error")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{session_id}")
def end_session(session_id: str) -> dict:
    _store.delete(session_id)
    return {"ok": True}
