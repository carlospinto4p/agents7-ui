import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from routers import catalog, engine, eval, run

app = FastAPI(title="agents7 UI backend")

_default_origins = "http://localhost:5173,http://localhost:8080"
_cors_origins = os.getenv("CORS_ORIGINS", _default_origins).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(run.router)
app.include_router(engine.router)
app.include_router(eval.router)

_README = Path(__file__).parents[2] / "agents7_framework" / "README.md"


@app.get("/api/readme", response_class=PlainTextResponse)
def get_readme() -> str:
    if not _README.exists():
        raise HTTPException(status_code=404, detail="README not found")
    return _README.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
