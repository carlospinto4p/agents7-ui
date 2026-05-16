import asyncio
import logging
import os

import httpx
from fastapi import APIRouter

router = APIRouter(prefix="/api/engine", tags=["engine"])
logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


@router.get("/models")
async def list_models() -> dict:
    async with httpx.AsyncClient() as client:
        try:
            tags_r, ps_r = await asyncio.gather(
                client.get(f"{OLLAMA_HOST}/api/tags", timeout=5.0),
                client.get(f"{OLLAMA_HOST}/api/ps", timeout=5.0),
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
