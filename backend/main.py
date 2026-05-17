import os
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from routers import catalog, chat, engine, eval, run

app = FastAPI(title="agents7 UI backend")

_default_origins = "http://localhost:5173,http://localhost:8080"
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

_UNPROTECTED = {"/api/health", "/api/engine/status"}


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
app.include_router(run.router)
app.include_router(engine.router)
app.include_router(eval.router)
app.include_router(chat.router)

_README = Path(__file__).parents[1] / "agents7_framework" / "README.md"


@app.get("/api/readme", response_class=PlainTextResponse)
def get_readme() -> str:
    if not _README.exists():
        raise HTTPException(status_code=404, detail="README not found")
    return _README.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
