
## Changelog - agents7 UI


### v0.2.0 - 9th May 2026

- Added `backend/routers/catalog.py`:
  - `GET /api/catalog/{agent_name}`: returns full agent details — system prompt, output model, output schema (via Pydantic `model_json_schema()`), system examples, and raw YAML source.
  - `find_config_file()`: shared helper to locate a config.yml by agent name (case-insensitive).
  - Updated `GET /api/catalog` list response to include `agent_type`.
- Added `backend/routers/run.py`: implemented `POST /api/run/{agent_name}` — loads catalog agent from YAML config, calls `act()` with request body as input, returns structured output and LLM metrics.
- Added `frontend/src/pages/Catalog.svelte`: full Catalog page with agent cards grid and inline Agent Detail view (system prompt, output schema, examples, YAML source).
- Updated `frontend/vite.config.js`: proxy `/api` to port 8001 for local dev.


### v0.1.0 - 3rd May 2026

- Added `backend/main.py`: FastAPI app with CORS middleware and health check.
- Added `backend/routers/`:
  - `catalog.py`: `GET /api/catalog` — auto-discovers agents from `agents_catalog/` by scanning `config.yml` files.
  - `engine.py`: placeholder `GET /api/engine/models`.
  - `run.py`: placeholder `POST /api/run/{agent_name}`.
- Added `frontend/src/App.svelte`: Svelte 5 SPA with hash-based routing for Catalog, Runner, Engine pages.
- Added `frontend/src/pages/`: placeholder Catalog, Runner, Engine components.
- Added Docker Compose with backend (Python/uvicorn) and frontend (Node/nginx) services.
