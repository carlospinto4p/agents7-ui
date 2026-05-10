
## Changelog - agents7 UI


### v0.8.2 - 10th May 2026

- Added page intro headers to all 6 tabs:
  - `Home`: title and summary linking to README content
  - `Catalog`: explains Catalog / Examples / Integration Test sections; added per-section descriptions in agent detail view (Output Schema, Examples, System Prompt, YAML Source)
  - `Runner`: explains Single vs Batch modes and JSONL format
  - `Chatter`: explains session-based chat, Reset, and token counts
  - `Engine`: explains Ollama, loaded vs idle model states, and VRAM column
  - `Eval`: explains golden datasets, accuracy bar, per-category breakdown, and mismatches


### v0.8.1 - 10th May 2026

- Fixed wide-screen layout across all pages: content no longer sticks to the
  left edge on large monitors:
  - `App.svelte`: header content wrapped in `.header-inner` (max-width 1400px,
    centred); `<main>` constrained to max-width 1400px with `margin: 0 auto`.
  - `Home.svelte`: `.readme` centred with `margin: 0 auto`.
  - `Catalog.svelte`: `.catalog` and `.detail` centred with `margin: 0 auto`.
  - `Chatter.svelte`, `Engine.svelte`, `Eval.svelte`: page containers
    centred with `margin: 0 auto`.


### v0.8.0 - 10th May 2026

- Added dark theme across all frontend files using CSS custom properties:
  - `app.css`: defined 19 design tokens (`--bg`, `--bg-surface`, `--bg-raised`, `--bg-header`, `--border`, `--text`, `--text-muted`, `--text-strong`, `--accent`, `--accent-dim`, and status vars `--pass/fail/warn` with `-bg` variants, `--neutral`).
  - `App.svelte`, `Catalog.svelte`, `Engine.svelte`, `Eval.svelte`, `Runner.svelte`: replaced all hardcoded hex colours with `var(--...)` tokens.
- Updated `public/favicon.svg`: dark `#16181d` numeral on accent blue background.


### v0.7.6 - 10th May 2026

- Added `frontend/public/favicon.svg`: SVG favicon — rounded blue square with white "7".
- Updated `frontend/index.html`: added `<link rel="icon">` pointing to `/favicon.svg`.


### v0.7.5 - 10th May 2026

- Fixed `frontend/src/App.svelte`:
  - `main`: added `flex: 1` so the background fills the full viewport on short pages.
  - `header`: added `position: sticky; top: 0; z-index: 10` so the nav stays visible when scrolling.


### v0.7.4 - 10th May 2026

- Added `frontend/src/app.css`: global CSS reset and base styles — system font stack, `box-sizing: border-box`, body background, link and form element defaults.
- Updated `frontend/src/main.js`: import `app.css`.


### v0.7.3 - 10th May 2026

- Removed `docker-compose.yml` backend `ports` mapping: backend port 8000 is no longer exposed to the host — it is only reachable from nginx inside the Docker network.


### v0.7.2 - 9th May 2026

- Refactored `routers/`:
  - Added `routers/utils.py`:
    - `_load_config()`: shared YAML config loader returning `(cfg, raw_yaml)`.
    - `_load_output_schema()`: shared output model resolver returning `(schema, fields)`.
  - Updated `catalog.py`: use `_load_config` in `_parse_summary`, `_parse_detail`, `find_config_file`; use `_load_output_schema` in `_parse_detail`.
  - Updated `eval.py`: use `_load_config` and `_load_output_schema` in `eval_agent`.


### v0.7.1 - 9th May 2026

- Refactored `backend/routers/`:
  - `eval.py`: narrowed `except Exception: pass` to `except (ImportError, AttributeError)` when loading output model schema; added `logger.warning()` with traceback before swallowing exceptions in `agent.act()`.
  - `catalog.py`: narrowed `except Exception: pass` to `except (ImportError, AttributeError)` when loading output model schema.


### v0.7.0 - 9th May 2026

- Added `frontend/src/pages/Eval.svelte`: Evaluation view — agent selector dropdown, Run Eval button, overall accuracy progress bar (green/yellow/red), per-category table sorted by accuracy, and mismatch list with input/expected/actual per row.
- Updated `frontend/src/App.svelte`: added Eval tab and route (`#/eval`).
- Fixed `frontend/package.json`: bumped version from 0.4.0 to 0.7.0 to match changelog.


### v0.6.0 - 9th May 2026

- Added `backend/routers/eval.py`: `POST /api/eval/{agent_name}` — discovers the agent's golden set (`data/golden_set.csv` or `.jsonl`), infers input vs. output columns from the output schema, runs the agent on every row, and returns `total`, `passed`, `failed`, `accuracy`, per-category breakdown, and a `mismatches` list.
- Updated `backend/main.py`: registered `eval` router.


### v0.5.0 - 9th May 2026

- Added `backend/routers/engine.py`: implemented `GET /api/engine/models` — queries Ollama `/api/tags` and `/api/ps`, returns merged list with `name`, `size`, `loaded`, `size_vram`, and `details` per model; returns `error` key when Ollama is unreachable.
- Added `httpx>=0.28.0` to `backend/pyproject.toml` and `Dockerfile.backend`.
- Updated `frontend/src/pages/Engine.svelte`: Engine status panel — shows all installed Ollama models in a table with size, loaded/idle badge, and VRAM usage; highlights loaded rows; auto-fetches on mount with a Refresh button.


### v0.4.0 - 9th May 2026

- Added `src/stores/history.js`: run-history store persisted to `localStorage`, max 50 entries, with `add()` and `clear()`.
- Updated `Runner.svelte`:
  - Single-input runner tab: input form derived from agent's first example, structured output card with key-value table.
  - Response history sidebar: collapsible, shows agent, mode, status, and timestamp for each run.
  - Batch runner now records a summary entry to history on completion.


### v0.3.0 - 9th May 2026

- Added `frontend/src/pages/Runner.svelte`: batch runner page — agent selector dropdown, JSONL textarea (paste or upload `.jsonl`), sequential per-row execution against `POST /api/run/{agent_name}`, live results table with `pass/fail/error` status badge and token count per row.


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
