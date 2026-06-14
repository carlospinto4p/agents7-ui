
## Changelog - agents7 UI


### v0.18.0 - 14th June 2026

- Added `backend/logging_setup.py`: file-based WARNING/ERROR logging
  following the canonical local-dev observability pattern.
  - `configure_logging()`: console + level-segregated rotating file
    handlers — WARNING → `logs/warnings/`, ERROR/CRITICAL →
    `logs/errors/`, one file per process start, UTC timestamps, clean
    level split. Attached to the root logger (captures `routers.*`)
    and to `uvicorn.error`.
  - Log root anchored to `$LOGS_DIR/logs`, falling back to
    `backend/logs/`.
- Updated `backend/main.py`: call `configure_logging()` at startup.
- Updated `docker-compose.yml`: `LOGS_DIR=/app` and bind-mount
  `./agents7_ui/logs:/app/logs` on the backend service.
- Added `backend/tests/test_logging.py`: env anchoring, clean level
  split, idempotency.
- Updated `.gitignore` (`logs/`, `*.log`) and `README.md` (Logs
  section).


### v0.17.2 - 13th June 2026

- `frontend/package.json`: aligned the pnpm pin `11.1.1` → `11.5.3`
  (fleet canonical version, matching corepack). The stale pin hard-failed
  `pnpm run build` — corepack's global default refuses to switch down.
  See the `pnpm-for-frontend` rule.


### v0.17.1 - 7th June 2026

- Updated `backend/routers/utils.py` `CHATTER_TYPE_MAP`: the
  legacy `personality_chatter` / `scene_chatter` agent types now
  map to `Chatter` (agents7 v4.0.0 removed the
  `PersonalityChatter` / `SceneChatter` classes; persona/scene
  are Chatter composition plugins). Existing configs with those
  agent types still load.


### v0.17.0 - 7th June 2026

- Show a persona/scene blurb for the selected agent on the Chatter
  page:
  - `backend/routers/catalog.py`: detail endpoint now returns the
    `persona` and `scene` config blocks.
  - `pages/Chatter.svelte`: fetches the agent detail on selection and
    renders a blurb (occupation · nationality, personality traits,
    backstory or system prompt, and scene setting for scene chatters).


### v0.16.2 - 7th June 2026

- Chatter page polish (`frontend/`):
  - `components/ChatPanel.svelte`: added `width: 100%` so the panel
    fills its container instead of shrinking to content width when the
    transcript is empty.
  - `pages/Chatter.svelte`: show the selected agent's summary (display
    name + type / provider / model / version badges) below the dropdown,
    not just the name.


### v0.16.1 - 7th June 2026

- Updated `components/ChatPanel.svelte`: assistant message bubbles now
  show response time alongside token count (`123 tok · 1.2s`), matching
  the metrics format used elsewhere in the catalog.


### v0.16.0 - 7th June 2026

- Added inline chat for chatter-family agents on the catalog detail
  page (`frontend/`):
  - `components/ChatPanel.svelte`: reusable multi-turn chat panel
    owning the `/api/chat` session lifecycle for one agent; seeds a
    ready-to-send sample message and exposes `restart()`.
  - `constants.js`: shared `CHATTER_TYPES` set and `isChatter()`.
  - `pages/Catalog.svelte`: chatter agents now embed `ChatPanel` plus
    an "Open in Chatter" deep link instead of a non-functional JSON
    input (the one-shot `/api/run` endpoint rejects chatter types);
    task agents gain a one-line guidance hint above the runner.
  - `pages/Chatter.svelte`: refactored onto `ChatPanel`; preselects an
    agent from a `#/chatter/<name>` deep link.


### v0.15.6 - 7th June 2026

- Removed the redundant `version` field from `frontend/package.json`:
  it drifted from the canonical app version in `backend/pyproject.toml`
  and was read by nothing — the version badge sources `/api/info`,
  which reads `backend/pyproject.toml`. The package is `private`, so no
  `version` field is required.


### v0.15.5 - 6th June 2026

- Fixed packaged catalog agents (e.g. Tagger agent) appearing twice in
  the catalog list:
  - `backend/routers/catalog.py`: the config scan now skips build /
    install artifacts (`build/`, `dist/`, `.venv`, `*.egg-info`,
    `__pycache__`, `site-packages`, `node_modules`), which each hold a
    duplicate `config.yml`.
  - `Dockerfile.backend`: remove in-tree `build/` and `*.egg-info`
    left by installing the catalog packages.
  - `backend/tests/test_catalog.py`: regression tests for
    `_is_catalog_config`.


### v0.15.4 - 6th June 2026

- `Dockerfile.backend`: install catalog agents that ship as packages so
  their custom `output_model` is importable at run time. Previously
  `POST /api/run/Tagger agent` failed with
  `ModuleNotFoundError: No module named 'tagger_agent'` because the
  image copied `agents_catalog/` without installing the agent packages.
  Each catalog package is now installed (`--no-deps`) plus its
  third-party runtime deps (`rapidfuzz`).


### v0.15.3 - 6th June 2026

- `frontend/src/pages/Catalog.svelte`: card grid is now a flex-wrap
  layout so a long agent title (e.g. `DemoTemperatureDetector`) widens
  its own card and stays on one line instead of wrapping; other cards
  keep their size.


### v0.15.2 - 6th June 2026

- `frontend/src/pages/Catalog.svelte`: reduced badge font size to
  `0.9rem` so the chips read as compact tags rather than body text.


### v0.15.1 - 6th June 2026

- Beautified the Catalog page badges and cards:
  - `frontend/src/pages/Catalog.svelte`: badges are now pill-shaped,
    lighter weight, and no longer uppercase, so long model names no
    longer overflow card margins. Model badges use a monospace font
    and wrap (`overflow-wrap`) instead of spilling outside the card.
    Cards gain a subtle hover lift and can shrink (`min-width: 0`) so
    their contents wrap cleanly within the grid.


### v0.15.0 - 6th June 2026

- Engine models table columns are now sortable:
  - `frontend/src/pages/Engine.svelte`: clicking the Name, Size,
    Status, or VRAM header sorts the table by that column; clicking
    again toggles ascending/descending. The active column shows a
    direction arrow. Status sorts loaded → loading → idle.


### v0.14.0 - 6th June 2026

- Engine model loading is now non-blocking and navigation-safe, with spinner icons:
  - `backend/routers/engine.py`: `POST /api/engine/load` fires the warm-up as a background task and returns `{"status": "loading"}` immediately, so large-model loads no longer risk a proxy timeout. In-flight loads are tracked server-side and surfaced via a new `loading` flag on each `GET /api/engine/models` entry — correct for any client and surviving page navigation.
  - `frontend/` (`Engine.svelte`): polls `/models` every 2s while any model is loading (and stops when none are); shows a spinner + "loading" badge and a disabled "Loading…" action while a model warms, plus spinner icons on the Refresh / Free all / row buttons while busy.
  - `backend/tests/test_security.py`: updated the load test for the background/`loading` contract and added a `loading`-flag test.


### v0.13.0 - 6th June 2026

- Engine model load/unload — free or wake the engine from the UI without touching the host process:
  - `backend/routers/engine.py`: added `POST /api/engine/load`, `/api/engine/unload`, and `/api/engine/unload-all`. Loading keeps a model resident (`keep_alive: -1`); unloading evicts it (`keep_alive: 0`) to free VRAM/RAM. Added the `ModelRef` body model and `_set_keep_alive()` helper.
  - `frontend/` (`Engine.svelte`): each model row gains a Load/Unload toggle, plus a "Free all" button to evict every loaded model.
  - `backend/tests/test_security.py`: added tests for load (`keep_alive -1`), unload (`keep_alive 0`), unreachable → 503, and unload-all evicting each loaded model.


### v0.12.6 - 6th June 2026

- `agents7_ui/README.md`: clarified that a single `0.0.0.0:11434` Ollama bind serves both the native and Docker Compose paths at once (no switching), replacing the earlier either/or framing and the needless docker-bridge suggestion.


### v0.12.5 - 6th June 2026

- Documented and prioritised the native (no-Docker) run path so Ollama can stay on plain `localhost` and the app runs without raising the Compose stack.
  - Added `agents7_ui/README.md` with "Run locally (no Docker)" and "Run with Docker Compose" sections.
  - `docker-compose.yml`: reverted `OLLAMA_HOST` from the hardcoded docker0 bridge IP back to `host.docker.internal` (+ `extra_hosts`), with a note that the Compose path needs a docker-reachable Ollama bind.
  - `agents7_ui/.env.example`: `OLLAMA_HOST` defaults to `http://localhost:11434` for native use.


### v0.12.4 - 6th June 2026

- Docker: scoped the host Ollama exposure to the docker0 bridge for security.
  - `docker-compose.yml`: backend targets `http://172.17.0.1:11434` (docker0) and dropped `extra_hosts`; the host service binds that bridge IP, so Ollama is reachable from containers but not on the host's LAN interfaces.
  - `agents7_ui/.env.example`: updated `OLLAMA_HOST` guidance to the docker0 bridge binding.


### v0.12.3 - 6th June 2026

- Docker: reverted the bundled in-container Ollama in favour of the host's Ollama service (which already holds the models and GPU); the in-container instance started empty and CPU-only.
  - `docker-compose.yml`: backend points at `host.docker.internal:11434`, restored `extra_hosts`, and dropped `ALLOW_ENGINE_START`, the `ollama_models` volume, and the GPU stanza.
  - `Dockerfile.backend`: removed the Ollama runtime install.
  - `agents7_ui/.env.example`: updated `OLLAMA_HOST` / `ALLOW_ENGINE_START` guidance — the host service must bind a docker-reachable address (e.g. `0.0.0.0:11434`), not loopback.
  - `POST /api/engine/start` and the Start button remain but are dormant (gated off); they apply only when the backend runs natively on a host with a local `ollama` binary.


### v0.12.2 - 6th June 2026

- `agents7_ui/.gitignore`: mirrored the `.env.*` ignore + `!.env.example` exception from the root ignore for defense-in-depth.


### v0.12.1 - 6th June 2026

- Environment variable configuration:
  - Added `agents7_ui/.env.example` documenting every variable (Ollama, CORS, `API_KEY`, provider keys, tuning), including the caveat that the bundled UI sends no auth header so `API_KEY` 401s it.
  - `docker-compose.yml`: backend loads an optional `agents7_ui/.env` via `env_file` and sets `CORS_ORIGINS` explicitly.
  - `.gitignore`: ignore all `.env.*` variants except the committed `.env.example`.


### v0.12.0 - 6th June 2026

- `backend/` (`routers/engine.py`):
  - Added `POST /api/engine/start`: starts a local `ollama serve` on demand, gated by the `ALLOW_ENGINE_START` env flag (default off), refusing a remote `OLLAMA_HOST` and a no-op when already running.
  - Added `_ollama_up()` and `_start_enabled()` helpers; `GET /api/engine/status` now also returns `can_start`.
- `frontend/` (`App.svelte`): Added a "Start" button beside the Ollama pill, shown only when Ollama is down and the server reports `can_start`; it posts to `/api/engine/start` and refreshes status.
- Docker:
  - `Dockerfile.backend`: bundled the Ollama runtime (needs `zstd` for the installer) so the backend can start it inside its own container.
  - `docker-compose.yml`: pointed the backend at in-container Ollama (`OLLAMA_HOST=http://localhost:11434`), enabled `ALLOW_ENGINE_START`, added a persistent `ollama_models` volume, and documented optional GPU passthrough.
- `backend/tests/test_security.py`: Added 4 tests for `POST /api/engine/start` (disabled by default, remote-host refusal, already-running no-op, spawn-and-started).


### v0.11.1 - 6th June 2026

- `frontend/` (`Home.svelte`): Removed the accent status dot from the version badge.


### v0.11.0 - 6th June 2026

- `frontend/` (`Home.svelte`):
  - Wrapped each top-level (`##`) README section in a collapsible `<details>`, collapsed by default, so the page is short and scannable; everything before the first section (title + intro) stays visible.
  - Assigned GitHub-style ids to all README headings so the in-README Table of Contents links resolve, and intercepted those clicks to expand the target section and scroll to it without touching `location.hash` (which the hash router would treat as navigation).
  - Restyled the version badge as an accent pill with a status dot.


### v0.10.1 - 6th June 2026

- `frontend/`: Moved the version badge out of the top bar (where it enlarged the header and broke its layout) into the `Home` page intro, beside the title.


### v0.10.0 - 6th June 2026

- `backend/main.py`:
  - Added `GET /api/info` returning `{name, version}`, with the version read from `pyproject.toml`.
  - Added `/api/info` to the unprotected route set so the badge loads without an API key.
- `frontend/`: Added a version badge to `App.svelte` that fetches `/api/info` on mount and renders `{name} v{version}` in document flow above the header.
- Fixed `font-size` floor: raised 112 sub-17px declarations across 9 frontend files to `1.0625rem` (17px) — v0.9.12 had enforced a 13px floor by mistake.
- `backend/tests/test_security.py`:
  - Fixed `test_engine_error_response_is_generic` to patch the module-level `_client` instead of the `httpx.AsyncClient` class (the class was patched after instantiation, so the test only passed when no Ollama was running).
  - Added `test_info_reports_name_and_version` and `test_info_version_matches_pyproject`.


### v0.9.12 - 18th May 2026

- Bumped all `font-size` rem values below `0.8125rem` to `0.8125rem` across 7 frontend files (`App.svelte`, `JsonViewer.svelte`, `Catalog.svelte`, `Chatter.svelte`, `Engine.svelte`, `Eval.svelte`, `Runner.svelte`) to enforce the accessibility floor.


### v0.9.11 - 17th May 2026

- Added provider/model badges to pipeline step card headers:
  - `frontend/src/pages/Catalog.svelte`: reads from `selected.step_engines[i]`.
  - `frontend/src/pages/Runner.svelte`: reads from `agentDetail.step_engines[i]`; added badge CSS.


### v0.9.10 - 17th May 2026

- Made pipeline step cards collapsible (expanded by default):
  - `frontend/src/pages/Catalog.svelte`: step headers are now buttons with a chevron; clicking toggles the input/output body.
  - `frontend/src/pages/Runner.svelte`: same collapsible behaviour in the single-run step breakdown.


### v0.9.9 - 17th May 2026

- Added pipeline step I/O breakdown to the Catalog inline runner:
  - `frontend/src/pages/Catalog.svelte`: after a pipeline run, shows the same numbered step cards (input/output tables, tok·duration) as the Runner page.
