"""Stateful chat sessions for Chatter-family agents."""

import asyncio
import json
import logging
import os
import re
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.util import find_spec
from pathlib import Path

import tomllib
from agents7.agents.config_loader import build_engine
from agents7.agents.utils import import_from_path
from agents7.eval.chat_review import (
    GuardAttempt,
    Recording,
    TurnRecord,
    save_recording,
)
from agents7.exceptions import Agents7Exception
from agents7.models.base import LLMMetrics
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from routers.catalog import CATALOG_PATH, find_config_file
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


def _clean_context(raw: object) -> dict[str, str]:
    """Normalise the per-conversation context from a start request.

    Blank entries are dropped rather than sent on, so a field the
    user left empty falls back to the agent's declared default
    instead of substituting an empty string into its prompt.

    :param raw: The request body's ``context`` value, of any shape.
    :return: Mapping of declared context name to a non-empty value.
    """
    if not isinstance(raw, dict):
        return {}
    cleaned = {}
    for key, value in raw.items():
        text = str(value).strip() if value is not None else ""
        if text:
            cleaned[str(key)] = text
    return cleaned


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

    ``pricing`` is kept only when the override names the agent's own
    provider *and* model — rates belong to one model, so carrying
    them onto a different one would report a confident price that is
    simply wrong. Dropping them leaves the turn unpriced, which the
    page shows by omitting the cost rather than printing a zero.
    Before this the rates were dropped even when the override
    resolved to the very model they were written for, so choosing
    the agent's own model made its cost disappear.

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
        if model == orig_engine.get("model") and "pricing" in orig_engine:
            override["pricing"] = orig_engine["pricing"]
    engine = build_engine(override)
    chatter._set_attr("engine", engine)


class _GuardCollector:
    """Collects the guard's metrics for the turn in progress.

    A guarded reply is at least two LLM calls — the chatter
    writes, the guard reads it and votes — and only the first is
    in the `ChatResponse`. Without this the UI reported roughly
    half of what a guarded turn actually cost, with nothing to
    say a half was missing.

    One collector is attached per session and reset at the start
    of each turn, since the framework's callback fires once per
    guard attempt and a rejected reply produces several.
    """

    def __init__(self) -> None:
        self.events: list[object] = []

    def __call__(self, event: object) -> None:
        self.events.append(event)

    @property
    def metrics(self) -> list[object]:
        """The metrics of every guard call that reported any."""
        return [
            e.metrics
            for e in self.events
            if getattr(e, "metrics", None) is not None
        ]

    def attempts(self) -> tuple[GuardAttempt, ...]:
        """The turn's guard checks, in the recording's own shape.

        Kept whole rather than reduced to a cost, because a saved
        conversation has to carry *why* the guard rejected a reply
        and what it suggested instead. Summing them to a number was
        enough while the only consumer was the metrics line.

        :return: One `GuardAttempt` per check.
        """
        return tuple(
            GuardAttempt(
                attempt=getattr(e, "attempt", 0),
                accepted=bool(getattr(e, "accepted", True)),
                reason=getattr(
                    getattr(e, "reason", None),
                    "value",
                    getattr(e, "reason", None),
                ),
                text=getattr(e, "response_text", ""),
                fix=getattr(e, "fix", None),
                used_fix=bool(getattr(e, "used_fix", False)),
                parse_failed=bool(getattr(e, "parse_failed", False)),
                metrics=(
                    e.metrics.model_dump()
                    if getattr(e, "metrics", None) is not None
                    else None
                ),
            )
            for e in self.events
        )

    def reset(self) -> None:
        self.events.clear()

    def summary(self) -> dict | None:
        """Total the guard calls made since the last reset.

        Adds them with `LLMMetrics.sum`, the framework's one
        aggregator, rather than field by field — this summed by
        hand until that existed, which made it a fourth place a
        new metric had to be remembered. It applies the rules
        that matter here: the guard half counts as cached only
        when every one of its calls was a hit, and an unpriced
        guard stays `None` rather than reading as free.

        `calls` is the collector's own: how many times the guard
        ran this turn, which is 1 on an accepted reply and more
        on a rejected one.

        :return: Totals for the turn, or ``None`` when the agent
            has no guard, so the UI can tell "no guard" apart
            from "a guard that cost nothing".
        """
        if not self.metrics:
            return None
        return {
            "calls": len(self.metrics),
            **LLMMetrics.sum(self.metrics).model_dump(),
        }


def _attach_guard_collector(chatter: object) -> None:
    """Give a guarded chatter a collector for its guard's cost.

    Plain chatters have no `guard_callback`, so they are left
    alone. The field is set through the framework's own escape
    hatch because a `Chatter` is a frozen dataclass.

    :param chatter: The chatter about to be stored in a session.
    """
    if not hasattr(chatter, "guard_callback"):
        return
    chatter._set_attr("guard_callback", _GuardCollector())


def _collector(chatter: object) -> _GuardCollector | None:
    """Return the chatter's guard collector, if it has one."""
    callback = getattr(chatter, "guard_callback", None)
    return callback if isinstance(callback, _GuardCollector) else None


def _begin_turn(chatter: object) -> None:
    """Drop the previous turn's guard metrics."""
    if (collector := _collector(chatter)) is not None:
        collector.reset()


def _metrics_dict(response: object, chatter: object = None) -> dict:
    """Serialise a `ChatResponse`'s metrics for the wire.

    :param response: A ChatResponse, or None when a stream finished
        without producing one.
    :param chatter: The chatter that produced it, so the guard's
        own calls can be reported beside the reply's. Omitted for
        an agent with no guard.
    :return: The metric fields the UI renders, or ``{}`` when there
        is no response to read them from.
    """
    if response is None:
        return {}
    metrics = response.metrics
    # Dumped rather than listed field by field. Listing them is
    # how the payload silently fell behind the framework twice —
    # once on `cached`, which made a cached turn render as a real
    # call that took no time and cost nothing, and once on the
    # cached token count.
    payload = metrics.model_dump()
    collector = _collector(chatter) if chatter is not None else None
    guard = collector.summary() if collector is not None else None
    if guard is not None:
        payload["guard"] = guard
        if metrics.cost_cents is not None and guard["cost_cents"] is not None:
            payload["total_cost_cents"] = (
                metrics.cost_cents + guard["cost_cents"]
            )
    return payload


#: A read id and a conversation id both become path segments, so
#: they are restricted to what cannot escape a directory.
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _package_root(config_file: Path) -> Path:
    """The agent package directory a config belongs to.

    Walks up from the config looking for the `pyproject.toml` that
    makes it a package, stopping at the catalog root. A config with
    no package above it (a sample, which ships no `pyproject.toml`)
    falls back to its own directory.

    :param config_file: Path to the agent's `config.yml`.
    :return: The directory a read folder should hang off.
    """
    root = CATALOG_PATH.resolve()
    here = config_file.resolve().parent
    while True:
        if (here / "pyproject.toml").is_file():
            return here
        if here == root or here.parent == here:
            return config_file.resolve().parent
        here = here.parent


def _package_version(config_file: Path) -> str:
    """The agent package's version, for stamping a recording.

    **Not** `Chatter.version`, which for a config-loaded agent is the
    config *schema* version — a recording came out stamped `1` that
    way once, and a recording's version is what tells two reads
    apart.

    :param config_file: Path to the agent's `config.yml`.
    :return: The version from its `pyproject.toml`, or `unknown`.
    """
    manifest = _package_root(config_file) / "pyproject.toml"
    if not manifest.is_file():
        return "unknown"
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return "unknown"
    return str((data.get("project") or {}).get("version") or "unknown")


@dataclass
class _Transcript:
    """A live chat session accumulating into a `Recording`.

    The Reads page can only show a conversation that was recorded in
    the framework's own shape — turns with their metrics, the guard's
    verdicts, and the context the agent ran with. A session held none
    of that: it answered each turn and forgot it, and the Chatter
    page's download wrote `{role, text}`, which no read can use.

    Built here rather than by driving the session through
    `ConversationRecorder`, which is the right tool when a script
    owns the loop. It does not fit this one: it replaces the
    chatter's `guard_callback` with its own collector, which this
    router needs for the per-turn metrics line, and it has no async
    or streaming path, while three of the four ways a turn arrives
    here are one or the other. Recording at the point each endpoint
    has its reply covers all four.

    :param agent: The agent's name from its config.
    :param agent_version: Its package version, not the config schema
        version — `Chatter.version` is the latter, which is how a
        recording once came out stamped `1`.
    :param config_file: Where the agent was loaded from, so a read
        can be saved beside it.
    :param context: What the context params resolved to when the
        session opened. Captured once: a resolver runs afresh on
        every read, so asking later could report a different time of
        day from the one the agent opened on.
    :param facts: The character facts the store already held.
    """

    agent: str
    agent_version: str
    config_file: Path
    context: dict[str, str] = field(default_factory=dict)
    facts: tuple[str, ...] = ()
    recorded: str = ""
    turns: list[TurnRecord] = field(default_factory=list)

    def record(
        self,
        prompt: str | None,
        response: object,
        attempts: tuple[GuardAttempt, ...],
        wall: float,
    ) -> None:
        """Append one finished turn.

        :param prompt: What the user wrote, or None for an opening.
        :param response: The `ChatResponse` the turn produced.
        :param attempts: The guard's checks on it.
        :param wall: Seconds measured around the call.
        """
        if response is None:
            return
        self.turns.append(
            TurnRecord(
                index=len(self.turns),
                prompt=prompt,
                reply=response.response,
                chatter=response.metrics.model_dump(),
                guard=attempts,
                wall_seconds=wall,
            )
        )

    def to_recording(self, conversation_id: str) -> Recording:
        """Build the recording this session amounts to.

        :param conversation_id: Its name within the read.
        :return: The `Recording`, ready to save.
        """
        return Recording(
            conversation_id=conversation_id,
            agent=self.agent,
            agent_version=self.agent_version,
            recorded=self.recorded,
            turns=tuple(self.turns),
            context=dict(self.context),
            facts=tuple(self.facts),
        )


class _SessionStore:
    _SESSION_TTL = 3600
    _MAX_STARTS = 20
    _RATE_WINDOW = 60
    _CLEANUP_INTERVAL = 300

    def __init__(self) -> None:
        self._sessions: dict[str, object] = {}
        self._transcripts: dict[str, _Transcript] = {}
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
            self._transcripts.pop(sid, None)
            self._session_times.pop(sid, None)

    async def run_periodic_cleanup(self) -> None:
        """Evict expired sessions on a fixed interval until cancelled.

        Complements the on-demand eviction in ``start_chat`` so idle
        sessions are reclaimed even when no new chats are started.
        """
        while True:
            await asyncio.sleep(self._CLEANUP_INTERVAL)
            self.evict_expired()

    def create(
        self, chatter: object, transcript: _Transcript | None = None
    ) -> str:
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = chatter
        if transcript is not None:
            self._transcripts[session_id] = transcript
        self._session_times[session_id] = time.monotonic()
        return session_id

    def get(self, session_id: str) -> object | None:
        return self._sessions.get(session_id)

    def transcript(self, session_id: str) -> _Transcript | None:
        """What this session has said so far, or None if untracked."""
        return self._transcripts.get(session_id)

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._transcripts.pop(session_id, None)
        self._session_times.pop(session_id, None)


_store = _SessionStore()


def _require_session(session_id: str) -> object:
    """Return the chatter for *session_id*, or raise a 404.

    :param session_id: The id handed out by `start_chat`.
    :return: The stored chatter instance.
    :raises HTTPException: 404 if the session expired or never
        existed.
    """
    chatter = _store.get(session_id)
    if chatter is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{session_id}' not found"
        )
    return chatter


def _can_remember(chatter: object) -> bool:
    """Report whether this chatter can record character facts.

    Mirrors the framework's own precondition for `remember()`: a fact
    store *and* an extractor. Read rather than caught, so the UI can
    hide the control instead of offering one that always fails.

    :param chatter: The session's chatter instance.
    :return: True when both are configured.
    """
    return (
        getattr(chatter, "facts", None) is not None
        and getattr(chatter, "fact_extractor", None) is not None
    )


def _require_can_remember(chatter: object) -> None:
    """Reject a remember request on an agent with no fact store.

    :param chatter: The session's chatter instance.
    :raises HTTPException: 422 if it has no store or no extractor.
    """
    if not _can_remember(chatter):
        raise HTTPException(
            status_code=422,
            detail=(
                "This agent does not record character facts. Give it a "
                "`character_facts` section in its config to let it "
                "remember what it said about itself."
            ),
        )


def _require_can_open(chatter: object) -> None:
    """Reject an opening turn on an agent that may not speak first.

    Checked before the reply starts rather than letting the
    framework raise mid-call, so the streaming route can answer with
    a status code instead of an error frame on an already-open
    response.

    :param chatter: The session's chatter instance.
    :raises HTTPException: 422 if its `can_open` is False.
    """
    if not getattr(chatter, "can_open", False):
        raise HTTPException(
            status_code=422,
            detail=(
                "This agent is not configured to open a conversation. "
                "Set `can_open: true` in its config to let it speak "
                "first."
            ),
        )


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
    """Open a chat session with an agent from the catalog.

    The optional JSON body carries a ``provider``/``model`` engine
    override and a ``context`` mapping of the per-conversation values
    the agent declares (its `context_params`). A context name the
    agent does not declare is rejected with a 400 rather than being
    silently ignored.

    The response reports ``can_open``: whether this agent may speak
    first, so the caller knows to offer the opening turn (see
    `open_turn`) instead of waiting for the user to type. It also
    reports ``can_remember``: whether the agent keeps a character
    fact store, so the caller knows to offer `remember_turn`.
    """
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
    context = _clean_context(body.get("context"))

    ChatterClass = import_from_path(class_path)
    try:
        chatter = ChatterClass.from_yaml(str(config_file))
        if provider:
            _apply_engine_override(
                chatter, cfg.get("engine") or {}, provider, model
            )
        if context:
            chatter.set_context(**context)
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

    _attach_guard_collector(chatter)
    # Captured here, at the session's start, because that is what the
    # conversation actually ran with: a `callable` context resolver
    # returns a fresh value on every read, and the fact store grows
    # if `remember` is called mid-session.
    transcript = _Transcript(
        agent=str(cfg.get("name") or agent_name),
        agent_version=_package_version(config_file),
        config_file=config_file,
        context=dict(getattr(chatter, "resolved_context", {}) or {}),
        facts=tuple(
            f.text for f in getattr(chatter, "character_facts", ()) or ()
        ),
        recorded=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    session_id = _store.create(chatter, transcript)
    engine = chatter.engine
    return {
        "session_id": session_id,
        "agent": cfg.get("name"),
        "provider": engine.provider,
        "model": engine.model_name,
        "can_open": bool(getattr(chatter, "can_open", False)),
        "can_remember": _can_remember(chatter),
    }


@router.post("/{session_id}/message")
async def send_message(session_id: str, request: Request) -> dict:
    chatter = _require_session(session_id)

    body = await request.json()
    message = body.get("message", "")
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    _begin_turn(chatter)
    started = time.perf_counter()
    try:
        response = chatter.chat(message)
    except Exception as exc:
        # Deliberately broad: a turn fails through the provider SDK as
        # often as through the framework, and those types are not
        # `Agents7Exception` — a revoked key, a rate limit, a model the
        # account cannot reach, an endpoint that is down. Without this
        # the route answered 500 with a traceback instead of the
        # generic detail below.
        logger.exception("Chat error in session %s", session_id)
        raise HTTPException(
            status_code=500, detail="Internal chat error"
        ) from exc

    _record_turn(
        session_id, message, response, chatter, time.perf_counter() - started
    )
    return {
        "response": response.response,
        "metrics": _metrics_dict(response, chatter),
    }


@router.post("/{session_id}/open")
async def open_turn(session_id: str) -> dict:
    """Let the agent speak first, with nothing to answer.

    Produces the opening line of the conversation, so the transcript
    starts with the agent rather than with the user. Only the agent's
    turn enters history. Call it once, before the first message; an
    agent whose `can_open` is False is rejected with a 422 rather
    than being made to invent an opening it was never given.

    :param session_id: The id handed out by `start_chat`.
    :return: The opening text and its turn metrics.
    """
    chatter = _require_session(session_id)
    _require_can_open(chatter)

    _begin_turn(chatter)
    started = time.perf_counter()
    try:
        response = await chatter.open_chat_async()
    except Exception as exc:
        # Broad for the same reason as `send_message` above: the
        # provider SDK's own error types are not `Agents7Exception`.
        logger.exception("Opening turn failed in session %s", session_id)
        raise HTTPException(
            status_code=500, detail="Internal chat error"
        ) from exc

    _record_turn(
        session_id, None, response, chatter, time.perf_counter() - started
    )
    return {
        "response": response.response,
        "metrics": _metrics_dict(response, chatter),
    }


@router.post("/{session_id}/remember")
async def remember_turn(session_id: str) -> dict:
    """Record what this conversation revealed about the character.

    Runs the agent's fact extractor over the transcript so far and
    writes the new facts to its store, where every later conversation
    picks them up. Deliberately a request the user makes rather than
    something the session does on its own: it costs an LLM call, the
    session is torn down and rebuilt on every agent, provider, model
    and context change, and only a person can say whether a given
    conversation was worth keeping.

    Safe to call twice — the store skips facts it already holds, so a
    second call on an unchanged transcript records nothing.

    :param session_id: The id handed out by `start_chat`.
    :return: ``facts``, the sentences written by this call (empty when
        the conversation revealed nothing new).
    """
    chatter = _require_session(session_id)
    _require_can_remember(chatter)

    try:
        written = await chatter.remember_async()
    except Exception as exc:
        # Broad for the same reason as `send_message` above: the
        # extractor runs an LLM call, so it fails through the provider
        # SDK as readily as through the framework.
        logger.exception("Recording facts failed in session %s", session_id)
        raise HTTPException(
            status_code=500, detail="Internal chat error"
        ) from exc

    return {"facts": [fact.text for fact in written]}


def _record_turn(
    session_id: str,
    prompt: str | None,
    response: object,
    chatter: object,
    wall: float,
) -> None:
    """Add one finished turn to the session's transcript.

    Called from each of the four ways a turn arrives — message,
    opening, and the streaming siblings of both — at the point that
    path has its reply. Best-effort on purpose: a session whose
    transcript could not be extended must still answer the turn, so
    this never raises into a chat.

    :param session_id: The session the turn belongs to.
    :param prompt: What the user wrote, or None for an opening.
    :param response: The `ChatResponse` produced.
    :param chatter: The chatter, for its guard collector.
    :param wall: Seconds measured around the call.
    """
    transcript = _store.transcript(session_id)
    if transcript is None:
        return
    collector = _collector(chatter)
    attempts = collector.attempts() if collector is not None else ()
    try:
        transcript.record(prompt, response, attempts, wall)
    except Exception:
        logger.exception("Could not record turn in session %s", session_id)


def _sse(data: dict, event: str | None = None) -> str:
    """Format a Server-Sent Events frame from a JSON payload."""
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _stream_turn(
    session_id: str,
    make_stream: Callable,
    chatter: object = None,
    prompt: str | None = None,
) -> StreamingResponse:
    """Wrap one streaming chatter call in an SSE response.

    Emits one ``data: {"delta": "..."}`` frame per text chunk, then a
    final ``event: done`` frame carrying the turn metrics. Any error
    mid-stream — the framework's or the provider SDK's — is reported as
    ``event: error`` rather than an HTTP status, since the response has
    already started.

    :param session_id: The session the turn belongs to, for logging.
    :param make_stream: Zero-argument coroutine function returning the
        chatter's async stream result (a reply or an opening turn).
    :param chatter: The chatter being streamed, so the guard's own
        calls reach the ``done`` frame alongside the reply's.
    :return: The Server-Sent Events response.
    """

    async def event_stream():
        try:
            if chatter is not None:
                _begin_turn(chatter)
            started = time.perf_counter()
            stream = await make_stream()
            async for chunk in stream:
                yield _sse({"delta": chunk})
            # After iteration: the reply is only parsed once the
            # stream is drained, so `chat_response` is None before it.
            _record_turn(
                session_id,
                prompt,
                stream.chat_response,
                chatter,
                time.perf_counter() - started,
            )
            yield _sse(
                {"metrics": _metrics_dict(stream.chat_response, chatter)},
                event="done",
            )
        except Exception:
            # Broad on purpose. A provider SDK error is not an
            # `Agents7Exception`, and letting one escape here breaks
            # the Server-Sent Events stream mid-response instead of
            # emitting the `event: error` frame the frontend renders.
            # `asyncio.CancelledError` derives from `BaseException`, so
            # a disconnecting client is still not caught here.
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


@router.post("/{session_id}/stream")
async def stream_message(
    session_id: str, request: Request
) -> StreamingResponse:
    """Stream a chat reply token-by-token via Server-Sent Events."""
    chatter = _require_session(session_id)

    body = await request.json()
    message = body.get("message", "")
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    return _stream_turn(
        session_id,
        lambda: chatter.chat_stream_async(message),
        chatter,
        prompt=message,
    )


@router.post("/{session_id}/open/stream")
async def stream_opening(session_id: str) -> StreamingResponse:
    """Stream the agent's opening turn, in the same frames as a reply.

    The streaming sibling of `open_turn`, so an agent that speaks
    first arrives token-by-token like every other turn.

    :param session_id: The id handed out by `start_chat`.
    :return: The Server-Sent Events response.
    """
    chatter = _require_session(session_id)
    _require_can_open(chatter)
    return _stream_turn(session_id, chatter.open_chat_stream_async, chatter)


@router.post("/{session_id}/save-read")
async def save_as_read(session_id: str, request: Request) -> dict:
    """Save this session's conversation as a read, on disk.

    The step that joins the two halves of the UI. Until now a
    conversation held here was answered and forgotten: the Reads page
    could only show what a script had recorded, so feeding back on a
    chat meant leaving the UI to record it again — and at temperature
    a re-run is a different conversation, so it could not be the same
    one.

    Writes the recording the Reads page already reads, beside the
    agent, under `docs/reads/<read_id>/<conversation_id>.json`. The
    session stays open; saving is a snapshot, not an ending, so a
    conversation can be saved and then continued.

    :param session_id: The id handed out by `start_chat`.
    :param request: JSON body with optional `read_id` and
        `conversation_id`.
    :return: Where it was written and what the Reads page needs to
        open it.
    """
    _require_session(session_id)
    transcript = _store.transcript(session_id)
    if transcript is None:
        raise HTTPException(
            status_code=404, detail="Session has no transcript"
        )
    if not transcript.turns:
        raise HTTPException(
            status_code=422, detail="Nothing said yet in this session"
        )

    body = await _optional_json(request)
    read_id = (
        str(body.get("read_id") or "").strip()
        or datetime.now(UTC).date().isoformat()
    )
    conversation_id = str(body.get("conversation_id") or "").strip() or "chat"
    for name, value in (
        ("read_id", read_id),
        ("conversation_id", conversation_id),
    ):
        if not _SAFE_NAME.match(value):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{name} must be 1-64 characters of letters, "
                    f"digits, dot, dash or underscore."
                ),
            )

    folder = (
        _package_root(transcript.config_file) / "docs" / "reads" / read_id
    )
    target = folder / f"{conversation_id}.json"
    if target.exists():
        raise HTTPException(
            status_code=409,
            detail=(
                f"{read_id}/{conversation_id}.json already exists. "
                f"Choose another name — a recording is paid for and "
                f"is never overwritten."
            ),
        )

    try:
        save_recording(transcript.to_recording(conversation_id), target)
    except OSError as exc:
        logger.exception("Could not save read for session %s", session_id)
        raise HTTPException(
            status_code=500, detail=f"Could not write the read: {exc}"
        ) from exc

    return {
        "path": str(folder.resolve().relative_to(CATALOG_PATH.resolve())),
        "read_id": read_id,
        "conversation_id": conversation_id,
        "turns": len(transcript.turns),
    }


@router.delete("/{session_id}")
def end_session(session_id: str) -> dict:
    _store.delete(session_id)
    return {"ok": True}
