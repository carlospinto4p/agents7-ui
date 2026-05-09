import os
from pathlib import Path

import yaml
from fastapi import APIRouter

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

# Local dev: repo-root/agents_catalog. Docker: override via CATALOG_PATH env.
_default = str(Path(__file__).parents[3] / "agents_catalog")
CATALOG_PATH = Path(os.getenv("CATALOG_PATH", _default))


def _parse_config(config_file: Path) -> dict:
    with open(config_file, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    engine = cfg.get("engine") or {}
    return {
        "name": cfg.get("name"),
        "version": cfg.get("version"),
        "provider": engine.get("provider"),
        "model": engine.get("model"),
    }


@router.get("")
def list_agents() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    return [
        _parse_config(c) for c in sorted(CATALOG_PATH.rglob("config.yml"))
    ]
