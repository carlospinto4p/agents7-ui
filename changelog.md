
## Changelog - agents7 UI


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


### v0.9.8 - 17th May 2026

- Added pipeline step I/O breakdown in the Runner single-run view:
  - `backend/routers/run.py`: pipeline response now includes `steps` array with per-step `name`, `input`, `output`, and `metrics`.
  - `frontend/src/pages/Runner.svelte`: when the result has steps, shows a numbered step cards section below the output card with input/output tables and token·duration metadata per step.


### v0.9.7 - 17th May 2026

- Fixed two pipeline detail regressions:
  - `frontend/src/pages/Catalog.svelte`: detail header badges now derive provider/model from `step_engines` for pipeline agents (same logic as the card), so badges are no longer lost when clicking through.
  - `agents_catalog/examples/person_to_bio_pipeline/config.yml`: added `output` to the system example so the Examples section shows the expected bio instead of `—`.


### v0.9.6 - 17th May 2026

- Fixed catalog card for pipeline agents:
  - `frontend/src/pages/Catalog.svelte`: card now derives provider and model badges from `step_engines` (unique values across steps) when `agent_type` is pipeline, so the Ollama/model badges appear correctly.
  - `frontend/src/pages/Catalog.svelte`: examples "out" row is always rendered; shows `—` when `ex.output` is null/undefined instead of hiding the row entirely.


### v0.9.5 - 17th May 2026

- Fixed three pipeline detail page gaps:
  - `backend/routers/catalog.py`: added `step_engines` (name, provider, model per step) to summary and detail API responses; refactored `_resolve_pipeline_steps` into `_resolve_pipeline_step_details` + `_pipeline_data`.
  - `backend/routers/run.py`: pipeline runs now aggregate token count, prompt tokens, and total duration across all step responses instead of returning all-`None` metrics.
  - `frontend/src/pages/Catalog.svelte`: examples section only renders the "out" row when `ex.output != null`; detail header shows per-step provider/model chain; `runnerMetaLine` uses step models for pipelines.


### v0.9.4 - 17th May 2026

- Added pipeline step display to catalog cards and detail headers:
  - `backend/routers/catalog.py`: added `_resolve_pipeline_steps()` and `_pipeline_steps()` helpers; `pipeline_steps` included in both summary and detail API responses.
  - `frontend/src/pages/Catalog.svelte`: card shows step chain (`step1 → step2`) below badges; detail header shows the same chain below the badge row.


### v0.9.3 - 17th May 2026

- Updated catalog card and detail header to show `persona.full_name` as
  display name when available, falling back to `name`:
  - `catalog.py`: added `_display_name()` helper; `_parse_summary()` and
    `_parse_detail()` now include `display_name` in the response.
  - `Catalog.svelte`: card title and detail `<h1>` use
    `display_name ?? name`.


### v0.9.2 - 17th May 2026

- Updated `frontend/src/pages/Runner.svelte` and `frontend/src/pages/Catalog.svelte`:
  - Added animated loading bar with elapsed-seconds counter while an agent is running.
  - Run button no longer shows "Running…" text — the loading bar replaces that role.
  - Output card header now shows elapsed time, token count, and model name (`5s · 312 tok · qwen3:8b`) once the run completes.
  - Empty-input guard: Run button stays disabled until all input fields have non-empty values.
  - Runner inputs are now pre-populated with the first example's values instead of showing them as placeholder hints.
  - Batch runner shows per-row progress and elapsed time below the button; total duration appears in the results header after completion.


### v0.9.1 - 17th May 2026

- Added Ollama availability indicator to the app header:
  - `backend/routers/engine.py`: new `GET /api/engine/status` endpoint — pings Ollama with a 2 s timeout, returns `{"available": bool}`.
  - `backend/main.py`: added `/api/engine/status` to `_UNPROTECTED` so it works without an API key.
  - `frontend/src/App.svelte`: grey/green/red pill in the top-right of the header; polls every 30 s via `onMount`.


### v0.9.0 - 17th May 2026

- Updated `frontend/src/pages/Catalog.svelte`:
  - Added inline **Runner** section to each agent's detail page (first section, open by default):
    - Per-field text inputs when the first example's input is a plain object.
    - Single text input when the first example's input is a plain string (wraps as `{input_data: value}` per API convention).
    - Raw JSON textarea fallback when no example input is available.
    - Output card with pass/fail badge, structured key-value table, parse-error raw response, and token count.
  - Added **collapsible sections**: Runner, Output Schema, Examples, System Prompt, YAML Source each have a toggle header with animated chevron. Runner/Schema/Examples default to open; System Prompt/YAML default to collapsed.


### v0.8.19 - 17th May 2026

- Added `frontend/src/components/JsonViewer.svelte`:
  - Syntax-highlighted JSON rendering with token colors: keys (blue), strings (green), numbers (amber), booleans/null (coral), punctuation (muted).
  - Uses `white-space: pre-wrap` + `overflow-wrap: anywhere` — no horizontal scrollbar.
  - Single vertical scroll with a 5px custom scrollbar (webkit + Firefox `scrollbar-width`).
- Updated `frontend/src/pages/Catalog.svelte`:
  - Replaced raw `<pre>{JSON.stringify(…)}</pre>` in the Output Schema section with `<JsonViewer>`.
  - Added custom thin scrollbar styles to `.code` (system prompt and YAML source blocks).


### v0.8.18 - 17th May 2026

- Refactored `routers/`:
  - `utils.py`: added `CHATTER_TYPE_MAP` (moved from `chat.py`).
  - `chat.py`: replaced module-level session dicts with `_SessionStore` class; use `_load_config` and `CHATTER_TYPE_MAP` from `utils`.
  - `run.py`: use `_load_config` from `utils` instead of inline `yaml.safe_load`.
  - `eval.py`: normalized unknown-`agent_type` error message to include valid types.
- Updated `tests/test_security.py`: rate-limit tests use `_store` instance.


### v0.8.17 - 17th May 2026

- Perf/refactor in `frontend/src/pages/`:
  - `Runner.svelte`: replace triple `.filter()` for `passCount`/`failCount`/`doneCount` (lines 196-198) with a single-pass `$derived.by()`.
  - `Runner.svelte`: replace chained `.split().map().filter().map()` in `parseLines()` with a single `for` loop.
  - `Catalog.svelte`: replace triple `.filter()` for agent grouping with a single-pass `reduce()`.
  - `Chatter.svelte` `$effect` audit: confirmed no hidden reactive dependencies — synchronous body reads no `$state`, so `agentName`/`starting` inside `.then()` are not tracked.


### v0.8.16 - 17th May 2026

- Performance improvements in `backend/routers/`:
  - `catalog.py`: build name-to-path index on first request; subsequent calls skip the `rglob` scan entirely.
  - `engine.py`: create module-level `httpx.AsyncClient` to reuse connection pool across requests.


### v0.8.15 - 17th May 2026

- Added `agents7_ui/backlog.md` so UI scan findings have a home.
- Updated `.claude/rules/`:
  - `improvement-areas.md`: added Svelte 5 `$effect` dependency leakage section with detection patterns and fix strategies.
  - `optimization-areas.md`: added bullet for `$effect` leakage causing cascading API calls.
  - `refactoring-areas.md`: added bullet for hidden reactive dependencies via function calls in effects.


### v0.8.14 - 17th May 2026

- Fixed `Chatter.svelte`: removed reactive `$effect` that tracked `starting` as an unintended dependency, causing an infinite `startSession()` cascade on every `starting` state change and 429 rate-limit errors.
  - Replaced with an explicit `startSession()` call at the end of the catalog load for the initial auto-start.
  - Agent-switch sessions are now handled solely by the `<select>` `onchange` handler.


### v0.8.13 - 17th May 2026

- Tightened page descriptions across all pages — dropped openers that restate the obvious and navigation instructions visible in the UI:
  - `Catalog.svelte`: removed "Browse all agents" and "Click any card"; trimmed detail-view section descriptions.
  - `Runner.svelte`: removed "Run catalog agents with custom inputs" opener and history-location sentence.
  - `Chatter.svelte`: removed "Chat with conversational agents" and "Token counts appear next to each reply"; kept Enter/Shift-Enter hint.
  - `Engine.svelte`: removed "Shows all models installed in Ollama" opener; kept Loaded/Idle definitions.
  - `Eval.svelte`: condensed two-sentence description into one.


### v0.8.12 - 17th May 2026

- Updated `Home.svelte`: replaced redundant "Home" title and navigation-instruction subtitle with "Framework" heading and a one-line description of the library.


### v0.8.11 - 17th May 2026

- Added `post_start` hook to `frontend` service in `docker-compose.yml`: prints `Frontend: http://localhost:8080` in the log stream when nginx starts.


### v0.8.10 - 17th May 2026

- Fixed `agents7_ui/.dockerignore`: added `frontend/node_modules` and `frontend/.svelte-kit` so Docker excludes them from the frontend build context (context is `agents7_ui/`, not repo root, so the root `.dockerignore` had no effect).


### v0.8.9 - 16th May 2026

- Refactored `agents7_ui/backend/routers/`:
  - Extracted `import_class()` and `AGENT_TYPE_MAP` from `run.py` into `utils.py`; `eval.py` now imports from the shared location instead of crossing into `run.py`
  - Narrowed broad `except Exception` catches: `run.py` catches `(AgentConfigurationError, PipelineConfigurationError, ValueError, ImportError)`; `chat.py` and `eval.py` catch `Agents7Exception`


### v0.8.8 - 16th May 2026

- Performance fixes (`/scan` pass):
  - `frontend/src/pages/Engine.svelte`: replaced `$effect(() => { fetchModels() })` with `onMount(fetchModels)` — `onMount` is the correct primitive for "run once on mount"; `$effect` is for reactive tracking.
  - `backend/routers/engine.py`: replaced two sequential `await client.get(...)` calls with `asyncio.gather(...)` to fetch `/api/tags` and `/api/ps` concurrently.


### v0.8.7 - 16th May 2026

- Fixed security issues in `agents7_ui/backend/routers/`:
  - `eval.py`: Log only input field keys on `agent.act()` failure; values omitted to prevent PII exposure.
  - `engine.py`: Return generic `"Could not reach model provider"` error to clients; log real exception internally.
  - `chat.py`: Added `_check_start_rate()` — per-IP rate limit of 20 session starts per 60 s (HTTP 429 on excess).
- Added regression tests in `tests/test_security.py` for all three fixes.
- Skipped backlog item 7 (`check_same_thread=False` on `SqliteCache`): flag is required for cross-thread use; the `threading.Lock()` serialises Python-level access but does not satisfy SQLite's internal thread check.


### v0.8.6 - 16th May 2026

- Fixed `backend/routers/run.py`: pipeline step `agent` paths now resolved and
  bounds-checked against `CATALOG_PATH`; paths containing `../../` that escape
  the catalog root raise a 422 error.
- Fixed `backend/main.py`: `CORS_ORIGINS` env var validated against
  `^https?://...` regex at startup; wildcards and malformed URLs raise
  `ValueError` instead of being passed to FastAPI silently.
- Added `backend/tests/test_security.py`: 11 unit tests covering both fixes.
- Added `pytest` to `backend/pyproject.toml` dev dependencies.


### v0.8.5 - 16th May 2026

- Hardened `backend/main.py` security posture:
  - CORS: restricted `allow_methods` to `["GET", "POST", "DELETE"]` and `allow_headers` to `["Content-Type", "Authorization"]` (was `["*"]` for both).
  - Auth: added `require_api_key` middleware — when `API_KEY` env var is set, all endpoints except `/api/health` require `Authorization: Bearer <key>`; no-op when unset (local dev unchanged).


### v0.8.4 - 13th May 2026

- Tightened pnpm security posture in `frontend/`:
  - `pnpm-workspace.yaml`: changed `allowBuilds.esbuild` from `true` to `false` — esbuild's `postinstall: node install.js` is now explicitly denied. esbuild's platform binary still ships via the `@esbuild/win32-x64` optional dependency, so `vite build` works unchanged.
  - `package.json`: removed the redundant `pnpm.onlyBuiltDependencies` block (the workspace-level `allowBuilds: esbuild: false` is the authoritative deny).
- Why: pnpm's whole point over npm is *no postinstall scripts unless explicitly approved*. The v0.8.3 entry that approved esbuild's postinstall defeated that and is reversed here.


### v0.8.3 - 13th May 2026

- Migrated `frontend/` from npm to pnpm (pinned via corepack):
  - `package.json`: added `packageManager: pnpm@11.1.1` and `pnpm.onlyBuiltDependencies: [esbuild]`.
  - Added `pnpm-workspace.yaml` with `allowBuilds.esbuild: true` (required by pnpm 11's build-approval check).
  - `pnpm-lock.yaml` replaces deleted `package-lock.json`.
  - `node_modules`: set NTFS `com.dropbox.ignored` ADS so Dropbox skips the directory from sync (replaces what would have been a junction to `D:\` — pnpm/Node fails with `ENOTDIR` on `fs.mkdir` against junctions in Dropbox-watched paths).
- Updated `Dockerfile.frontend`: switched from `npm install` / `npm run build` to corepack-managed pnpm with `--frozen-lockfile`; added `pnpm-lock.yaml` and `pnpm-workspace.yaml` to the deps-cache `COPY` stage.
- Part of the cross-project npm → pnpm standardization (pilot repo).


