"""Stateful chat sessions for Chatter-family agents."""

import asyncio
import json
import logging
import os
import time
import uuid
from importlib.util import find_spec

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agents7.agents.config_loader import build_engine
from agents7.agents.utils import import_from_path
from agents7.exceptions import Agents7Exception
from routers.catalog import find_config_file
from routers.utils import CHATTER_TYPE_MAP, _load_config

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)

# Providers a chat session can be started with. Ollama is always
# offered (its models are managed on the Engine page); the API-backed
# providers depend on their SDK package plus credentials in the
# environment — see `_provider_status`.
_PROVIDERS = ("ollama", "anthropic", "openai_compat")

# Engine-section keys that describe the connection to a specific
# provider (as opposed to provider-agnostic behaviour like retry /
# cache). These are only carried over into an override when the
# provider is unchanged.
_CONNECTION_KEYS = ("base_url", "api_key", "fallback_model")


def _provider_status(provider: str) -> dict:
    """Report whether *provider* can be used for a chat override.

    :param provider: One of ``_PROVIDERS``.
    :return: A dict with the provider ``name``, a ``ready`` flag, a
        ``detail`` string explaining why it is not ready (empty when
        ready), and — for ``openai_compat`` — the ``model`` read from
        the environment (``None`` if unset), so the UI can make the
        model field optional.
    """
    if provider == "anthropic":
        has_pkg = find_spec("anthropic") is not None
        has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
        detail = ""
        if not has_pkg:
            detail = "anthropic package not installed"
        elif not has_key:
            detail = "ANTHROPIC_API_KEY not set"
        return {
            "name": provider,
            "ready": has_pkg and has_key,
            "detail": detail,
        }
    if provider == "openai_compat":
        has_pkg = find_spec("openai") is not None
        has_key = bool(
            os.getenv("OPENAI_COMPAT_API_KEY") or os.getenv("OPENAI_API_KEY")
        )
        detail = ""
        if not has_pkg:
            detail = "openai package not installed"
        elif not has_key:
            detail = "OPENAI_COMPAT_API_KEY / OPENAI_API_KEY not set"
        return {
            "name": provider,
            "ready": has_pkg and has_key,
            "detail": detail,
            "model": os.getenv("OPENAI_COMPAT_MODEL_NAME") or None,
        }
    # ollama: assumed reachable; the Engine page surfaces its status.
    return {"name": provider, "ready": True, "detail": ""}


async def _optional_json(request: Request) -> dict:
    """Return the request's JSON body, or ``{}`` if there is none.

    The chat-start request carries an optional engine override; an
    empty body (the common case) must not raise.
    """
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


def _apply_engine_override(
    chatter: object, orig_engine: dict, provider: str, model: str
) -> None:
    """Swap the chatter's response engine for one built from overrides.

    Provider-agnostic settings (``retry``, ``cache``) are carried over
    from the agent's configured engine. Connection settings
    (``base_url`` / ``api_key`` / ``fallback_model``) are only kept
    when the provider is unchanged, since they are meaningless across
    a provider switch — the new provider reads its credentials from the
    environment instead. For ``GuardedChatter``-family agents this
    changes only the reply model; the guard keeps its own configured
    engine.

    :param chatter: The loaded chatter instance to mutate.
    :param orig_engine: The ``engine`` section from the agent's config.
    :param provider: The override provider (e.g. ``"ollama"``).
    :param model: The override model name (may be empty for
        ``openai_compat``, which then reads the environment).
    :raises ValueError: If the provider/model combination is invalid.
    """
    override: dict = {"provider": provider, "model": model or None}
    for key in ("retry", "cache"):
        if key in orig_engine:
            override[key] = orig_engine[key]
    if provider.lower() == str(orig_engine.get("provider", "")).lower():
        for key in _CONNECTION_KEYS:
            if key in orig_engine:
                override[key] = orig_engine[key]
    engine = build_engine(override)
    chatter._set_attr("engine", engine)


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


@router.get("/providers")
def list_providers() -> dict:
    """List the providers a chat session may be started with.

    Each entry reports whether the provider is ready to use (its SDK
    package is installed and any required credentials are present in
    the environment), so the UI can guide the user toward a working
    override instead of failing on the first message.
    """
    return {"providers": [_provider_status(p) for p in _PROVIDERS]}


@router.post("/start/{agent_name}")
async def start_chat(agent_name: str, request: Request) -> dict:
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

    body = await _optional_json(request)
    provider = str(body.get("provider") or "").strip()
    model = str(body.get("model") or "").strip()

    ChatterClass = import_from_path(class_path)
    try:
        chatter = ChatterClass.from_yaml(str(config_file))
        if provider:
            _apply_engine_override(
                chatter, cfg.get("engine") or {}, provider, model
            )
    except (Agents7Exception, ImportError, ValueError) as exc:
        logger.warning(
            "Could not start chat for %s with provider=%r model=%r: %s",
            agent_name,
            provider,
            model,
            exc,
        )
        raise HTTPException(
            status_code=400, detail=f"Could not start chat: {exc}"
        ) from exc

    session_id = _store.create(chatter)
    engine = chatter.engine
    return {
        "session_id": session_id,
        "agent": cfg.get("name"),
        "provider": engine.provider,
        "model": engine.model_name,
    }


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
            "cost_cents": response.metrics.cost_cents,
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
                    "cost_cents": resp.metrics.cost_cents,
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
