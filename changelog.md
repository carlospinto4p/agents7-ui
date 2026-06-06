
## Changelog - agents7 UI


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


