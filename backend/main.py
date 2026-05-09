from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import catalog, engine, eval, run

app = FastAPI(title="agents7 UI backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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
