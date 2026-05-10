import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
