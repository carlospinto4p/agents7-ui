import asyncio
import logging
import os
import subprocess
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/engine", tags=["engine"])
logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
_client = httpx.AsyncClient()

# Hostnames for which `ollama serve` can be started in this process's
# own environment (same machine / same container).
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _start_enabled() -> bool:
    """Whether starting the engine is permitted.

    Gated by the ``ALLOW_ENGINE_START`` env var so the
    process-spawning surface is inert unless the operator opts in.

    :return: ``True`` when the flag is set to a truthy value.
    """
    return os.getenv("ALLOW_ENGINE_START", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


async def _ollama_up() -> bool:
    """Check whether Ollama answers at `OLLAMA_HOST`.

    :return: ``True`` if `/api/tags` responds successfully.
    """
    try:
        r = await _client.get(f"{OLLAMA_HOST}/api/tags", timeout=2.0)
        return r.is_success
    except Exception:
        return False


@router.get("/models")
async def list_models() -> dict:
    try:
        tags_r, ps_r = await asyncio.gather(
            _client.get(f"{OLLAMA_HOST}/api/tags", timeout=5.0),
            _client.get(f"{OLLAMA_HOST}/api/ps", timeout=5.0),
        )
    except Exception as exc:
        logger.warning(
            "Failed to reach model provider at %s: %s", OLLAMA_HOST, exc
        )
        return {"models": [], "error": "Could not reach model provider"}

    tags = tags_r.json().get("models", []) if tags_r.is_success else []
    loaded_list = ps_r.json().get("models", []) if ps_r.is_success else []
    loaded_map = {m["name"]: m for m in loaded_list}

    models = []
    for m in tags:
        name = m["name"]
        loaded_info = loaded_map.get(name)
        models.append(
            {
                "name": name,
                "size": m.get("size"),
                "loaded": name in loaded_map,
                "size_vram": (
                    loaded_info.get("size_vram") if loaded_info else None
                ),
                "details": m.get("details"),
            }
        )

    return {"models": models}


@router.get("/status")
async def ollama_status() -> dict:
    return {
        "available": await _ollama_up(),
        "can_start": _start_enabled(),
    }


@router.post("/start")
async def start_ollama() -> dict:
    """Start a local `ollama serve` process if it is not already up.

    Refuses unless `ALLOW_ENGINE_START` is set, and only when
    `OLLAMA_HOST` points at this machine — a remote Ollama cannot be
    started from here. Idempotent: a no-op if Ollama already responds.

    :raises HTTPException: 403 when disabled, 400 for a remote host,
        500 if the `ollama` binary is missing, 504 if it does not
        become ready in time.
    :return: ``{"status": "already_running" | "started"}``.
    """
    if not _start_enabled():
        raise HTTPException(
            status_code=403,
            detail="Engine start is disabled. "
            "Set ALLOW_ENGINE_START=1 to enable.",
        )

    host = urlparse(OLLAMA_HOST).hostname
    if host not in _LOCAL_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="OLLAMA_HOST is remote; cannot start it locally.",
        )

    if await _ollama_up():
        return {"status": "already_running"}

    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="ollama binary not found on PATH.",
        ) from exc

    for _ in range(20):
        await asyncio.sleep(0.5)
        if await _ollama_up():
            logger.info("Started ollama serve at %s", OLLAMA_HOST)
            return {"status": "started"}

    raise HTTPException(
        status_code=504,
        detail="Ollama did not become ready in time.",
    )
