
## Changelog - agents7 UI


### v0.20.5 - 11th July 2026

- Fixed test-suite log pollution in `backend/`:
  - `tests/conftest.py`: redirect `LOGS_DIR` to a throwaway dir at
    conftest import time, so importing `main` (which calls
    `configure_logging()`) no longer installs file handlers rooted at
    the committed `backend/logs/` tree. Router tests that trigger
    warnings previously persisted them there and tripped the
    session-start container-log check.
  - `tests/test_logging.py`: added
    `test_session_logs_redirected_out_of_source_tree()` regression
    guard.
- Added `.claude/skills/fix-errors/`: per-project skill to triage the
  backend's `logs/errors/` and `logs/warnings/` (read → diagnose →
  fix → delete), adapting the canonical container-log fix loop to the
  agents7 UI backend domain.


### v0.20.4 - 21st June 2026

- Refactored `backend/routers/` to drop the last local copies of
  framework agent-resolution glue:
  - `run.py`: structured-agent resolution now uses
    `agents7.eval.AGENT_TYPE_MAP` + `build_agent` instead of the
    local `AGENT_TYPE_MAP` / `import_class`; the `pipeline` branch
    is preserved.
  - `run.py` / `chat.py`: dotted-path class loading now uses the
    framework's `import_from_path` (adds an injection guard on
    user-supplied YAML `agent_type` paths) in place of the local
    `import_class`.
  - `utils.py`: removed the duplicated `AGENT_TYPE_MAP` and
    `import_class`; only `CHATTER_TYPE_MAP` (no framework
    equivalent) remains.
  - `tests/test_utils.py`: dropped the `import_class` tests (the
    behaviour is now covered by the framework suite).


### v0.20.3 - 21st June 2026

- Refactored `backend/routers/eval.py` to reuse the framework's
  `agents7.eval` public API instead of local copies:
  - Replaced `_load_golden_set` with `load_eval_rows`, the inline row
    normalisation with `normalise_rows`, the output-field resolution with
    `model_output_fields`, and the agent construction with `build_agent`.
  - `AGENT_TYPE_MAP` now comes from `agents7.eval` rather than
    `routers.utils`.
  - Fixed a latent crash in the failure-logging path: a scalar input is
    logged as `["<input>"]` instead of calling `.keys()` on a string.


### v0.20.2 - 21st June 2026

- Repinned ports to comply with `default-ports.md` (never bind a
  service's shared default):
  - `docker-compose.yml`: frontend host port `8080` → registry-claimed
    `${FRONTEND_PORT:-5185}`; the `ports` mapping, `CORS_ORIGINS` default,
    and the `post_start` startup banner now read the one variable so they
    cannot drift (`docker-compose-startup-ports.md` source-of-truth).
  - `frontend/vite.config.js`: pinned dev server `port` to `5186` (never
    the shared Vite `5173` default).
  - `backend/main.py`: updated `_default_origins` to `5186,5185`.
- Updated `README.md` and `.env.example`: document `FRONTEND_PORT` and the
  new dev/compose ports.
- Updated `tests/test_security.py`: sample CORS origins use the new ports.


### v0.20.1 - 21st June 2026

- `frontend/package.json`: bumped the pinned pnpm to `11.8.0` to match
  this machine's corepack canonical version. The stale `11.5.3` pin
  hard-fails `pnpm` builds under corepack (the corepack trap in
  `pnpm-for-frontend.md`); part of the fleet-wide sweep.


### v0.20.0 - 14th June 2026

- Added `frontend/src/lib/format.js`: shared `fmtCost`,
  `metricsLine`, `copyText`, `downloadText`, and `downloadJson`
  helpers.
- Added cost display: run (single + steps) and chat metrics now
  show `cost_cents` when present (omitted for local providers
  that report no cost).
  - `backend/routers/chat.py`: include `cost_cents` in the chat
    stream `done` frame and the `/message` response metrics.
- Added export & copy:
  - Download JSON for run output, batch results, eval results,
    and chat transcripts.
  - Copy-to-clipboard buttons on the run output and YAML source
    blocks.
- Added a catalog search/filter box that filters agents by name,
  type, provider, or model.


### v0.19.0 - 14th June 2026

- Added token-by-token chat streaming:
  - `backend/routers/chat.py`: new `POST /api/chat/{session_id}/stream`
    endpoint that streams the reply as Server-Sent Events (one
    `delta` frame per chunk, a final `done` frame with metrics,
    and an `error` frame on framework failure). Built on the
    framework's `chat_stream_async`.
  - `frontend/src/components/ChatPanel.svelte`: consume the SSE
    stream, appending tokens to a live assistant bubble instead
    of waiting for the whole response.
  - `backend/tests/test_chat.py`: cover the SSE framing and the
    delta / done / error paths.


### v0.18.5 - 14th June 2026

- Added `backend/tests/test_utils.py`: error-path coverage for
  `import_class` (missing module, missing attribute, malformed dotted
  path) and `_load_output_schema` (absent/empty path, suppressed
  import/attribute errors, valid-model schema).


### v0.18.4 - 14th June 2026

- `frontend/src/pages/Catalog.svelte`, `Chatter.svelte`: moved the
  top-level `/api/catalog` fetch from a `$effect` to `onMount`, so the
  one-time load can never re-fire on unrelated state changes. The
  `agentName`-driven detail fetch in `Chatter.svelte` stays a
  reactive `$effect` (it correctly depends on the selection).


### v0.18.3 - 14th June 2026

- `backend/routers/utils.py`: added the `-> type` return annotation
  to `import_class`.
- `backend/routers/catalog.py`: `_resolve_pipeline_step_details` now
  logs a warning when a step config can't be read instead of
  swallowing the error silently (listing stays resilient).
- Added `tests/test_security.py`: malformed-step-config resilience.


### v0.18.2 - 14th June 2026

- `backend/main.py`:
  - Cached `/api/info` version via `_read_version()` (`lru_cache`) —
    `pyproject.toml` is read once, not per request.
  - Cached `/api/readme` via `_read_readme()` (`lru_cache`) —
    `README.md` is read once, not per request.
  - Added an app lifespan that runs a periodic chat-session cleanup
    task.
- `backend/routers/chat.py`: added `_SessionStore.run_periodic_cleanup()`
  (evicts expired sessions every 5 min), complementing the on-demand
  eviction so idle sessions are reclaimed without new chats.
- Added `tests/test_security.py` cases: version/README caching, expired
  eviction, periodic cleanup.


### v0.18.1 - 14th June 2026

- Fixed path traversal in catalog pipeline-step display:
  - `routers/utils.py`: extracted `_resolve_agent_path()` (shared
    guard, with an `allow_absolute` flag) from `run.py`.
  - `routers/catalog.py`: `_resolve_pipeline_step_details` now
    resolves step paths through the guard (`allow_absolute=False`)
    and skips reading any path escaping the catalog root, so a
    crafted pipeline config can no longer leak arbitrary files.
  - `routers/run.py`: imports the shared guard (behaviour
    unchanged).
- Added `tests/test_security.py` cases for the catalog guard and the
  absolute-path rejection.


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
