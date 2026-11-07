import asyncio
import functools
import os
import re
import tomllib
from contextlib import asynccontextmanager
from importlib import metadata
from pathlib import Path

# Must precede every import below: reads the repository's `.env` into the
# environment, and `logging_setup` / `routers.engine` /
# `routers.catalog` all read variables at import time.
import env_setup  # noqa: F401
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from logging_setup import configure_logging
from routers import catalog, chat, classes, engine, eval, reads, run

configure_logging()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Run a periodic chat-session cleanup task for the app's lifetime."""
    task = asyncio.create_task(chat._store.run_periodic_cleanup())
    try:
        yield
    finally:
        task.cancel()


app = FastAPI(title="agents7 UI backend", lifespan=_lifespan)

_default_origins = "http://localhost:5186,http://localhost:5185"
_ORIGIN_RE = re.compile(r"^https?://[a-zA-Z0-9._-]+(:\d{1,5})?$")


def _parse_cors_origins(raw: str) -> list[str]:
    origins = []
    for o in raw.split(","):
        o = o.strip()
        if not o:
            continue
        if not _ORIGIN_RE.match(o):
            raise ValueError(f"Invalid CORS origin in CORS_ORIGINS: {o!r}")
        origins.append(o)
    return origins


_cors_origins = _parse_cors_origins(
    os.getenv("CORS_ORIGINS", _default_origins)
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

_UNPROTECTED = {"/api/health", "/api/engine/status", "/api/info"}


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    api_key = os.getenv("API_KEY")
    if (
        api_key
        and request.method != "OPTIONS"
        and request.url.path not in _UNPROTECTED
    ):
        auth = request.headers.get("Authorization", "")
        if auth != f"Bearer {api_key}":
            return JSONResponse(
                status_code=401, content={"detail": "Unauthorized"}
            )
    return await call_next(request)


app.include_router(catalog.router)
app.include_router(classes.router)
app.include_router(run.router)
app.include_router(engine.router)
app.include_router(eval.router)
app.include_router(chat.router)
app.include_router(reads.router)


@functools.lru_cache(maxsize=1)
def _read_readme() -> str:
    """Read the framework README from the installed `agents7` package.

    The framework is a dependency, not a sibling folder, so its README
    comes from the package metadata (its long description). Cached; it
    never changes at runtime.

    :return: The README text.
    :raises LookupError: If `agents7` is not installed or carries no
        README.
    """
    try:
        text = metadata.metadata("agents7").get_payload()
    except metadata.PackageNotFoundError as exc:
        raise LookupError("agents7 is not installed") from exc
    if not text:
        raise LookupError("agents7 carries no README")
    return text


@app.get("/api/readme", response_class=PlainTextResponse)
def get_readme() -> str:
    try:
        return _read_readme()
    except LookupError:
        raise HTTPException(status_code=404, detail="README not found")


_PYPROJECT = Path(__file__).parent / "pyproject.toml"


@functools.lru_cache(maxsize=1)
def _read_version() -> str:
    """Read the app version from ``pyproject.toml`` (cached).

    The version is fixed for a process, so it is read once and
    cached.

    :return: The semver string, or ``"unknown"`` if it cannot be read.
    """
    try:
        data = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
        return data["project"]["version"]
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


@app.get("/api/info")
def get_info() -> dict:
    return {"name": "agents7-ui", "version": _read_version()}


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
