
## Changelog - agents7 UI


### v0.26.2 - 18th July 2026

- Filled in `roadmap.md`, which was still an `init-project` stub:
  - Current phase: frontend e2e test harness (gating new interactive
    features), then making the Eval page a first-class consumer of
    `agents7.eval` (gating duplicated eval logic).
  - Standing invariants: the UI stays a thin, introspecting view over
    the framework; provider-agnostic by default; the backend is never
    host-exposed in Compose; registry-claimed host ports; first-party
    backend records only in `logs/`; 17px raw-text floor.
  - Refuted directions: version badge in or above the top bar
    (v0.10.1), a second source of the app version, and `$effect`
    blocks calling `$state`-reading helpers.


### v0.26.1 - 13th July 2026

- Rotated changelog: archived 18 entries to `changelog/2026.md`.


### v0.26.0 - 12th July 2026

- Added an engine override to the **Chatter** page — chat with any
  provider/model instead of the one baked into the agent config:
  - `backend/routers/chat.py`: `POST /api/chat/start/{agent}` now
    accepts an optional `{provider, model}` body and swaps the reply
    engine via `_apply_engine_override()` (retry/cache carry over;
    connection settings only within the same provider; the guard keeps
    its own engine). Returns the effective `provider`/`model`.
  - `backend/routers/chat.py`: new `GET /api/chat/providers` reporting
    each provider's readiness (SDK installed + credentials in the env).
  - `backend/pyproject.toml`: depend on `agents7[anthropic,openai]` so
    the API providers are usable.
  - `frontend/src/components/ChatPanel.svelte`: `provider`/`model`
    props sent on session start; changing either restarts the session.
  - `frontend/src/pages/Chatter.svelte`: Provider + Model selectors
    (Ollama picks from installed models, API providers take a free
    model name), with a readiness warning for unconfigured providers.
- Updated the **Chatter** agent dropdown to show each agent's class
  type alongside its name.
- Added `backend/tests/test_chat.py` tests for the override helper,
  provider-status reporting, and the optional-body parser.


### v0.25.0 - 12th July 2026

- Enhanced the **Agent Classes** page to show field inheritance:
  - `backend/routers/agent_fields.py`: new `build_fields()` attributes
    each agent's dataclass fields to the ancestor class that introduced
    them, pairing each with the most specific description across the
    inheritance chain's docstrings.
  - `GET /api/classes` now returns `fields` (name, type, description,
    `owner`, `inherited`) per class; docstring attribute/parameter
    blocks are superseded by it, with only note prose kept in
    `sections`.
  - `Classes.svelte`: renders fields grouped by origin — "inherited
    from `BaseAgent`", "inherited from `Labeler`", "defined here" — as
    collapsible groups with per-group field counts.
  - Renders reST inline code (`` `name` `` / ` ``name`` `) in
    descriptions and field text as `<code>` instead of literal
    backticks.
  - The selected class is now deep-linkable as `#/classes/<ClassName>`.
- Added tests:
  - `tests/test_agent_fields.py`: 6 tests for field attribution.
  - `tests/test_classes.py`: updated for the `fields` shape.


### v0.24.1 - 12th July 2026

- Improved the **Agent Classes** page:
  - Switched the hierarchy diagram to a horizontal (left→right) tree —
    the abstract root anchors the left, depth grows rightward.
  - `backend/routers/docstrings.py`: new `parse_docstring()` that
    normalises Google-style (`Attributes:` / `Note:`) and Sphinx
    (`:param:`) docstrings into structured sections.
  - `GET /api/classes` now returns each class's `description` and
    parsed `sections` alongside the raw `doc`.
  - `Classes.svelte`: renders attributes/parameters as a field list
    with type badges and notes as prose, instead of raw docstring text.
- Added tests:
  - `tests/test_docstrings.py`: 9 tests for the docstring parser.
  - `tests/test_classes.py`: assert `description`/`sections` are parsed.


### v0.24.0 - 12th July 2026

- Added an **Agent Classes** page — a diagram of the framework's agent
  class hierarchy:
  - `backend/routers/classes.py`: `GET /api/classes` introspects
    `BaseAgent.__subclasses__()` at runtime (name, parent, module,
    abstract flag, summary, docstring) so the tree needs no hardcoded
    list and always matches the installed framework.
  - `frontend/src/pages/Classes.svelte`: tidy top-down SVG tree with
    family colouring, dashed abstract nodes, and a click-to-inspect
    detail panel showing the inheritance chain and docstring.
  - Registered the route in `App.svelte` and a nav entry in
    `Sidebar.svelte`.
- Added `tests/test_classes.py`: 6 tests covering the hierarchy
  endpoint.


### v0.23.1 - 12th July 2026

- Fixed the Runner listing conversational (chatter-family) agents,
  which have no input schema and left the Run button permanently
  disabled when one was auto-selected:
  - Updated `frontend/src/pages/Runner.svelte`: exclude
    chatter-family agents (via `isChatter`) from both dropdowns and
    the default selection, so the Runner only offers one-shot
    `/api/run` agents. Chatters belong in the Chatter tab.
  - The agent picker now shows the `display_name` and an
    `agent_type` badge, matching the Catalog and Chatter pages.


### v0.23.0 - 12th July 2026

- Added agent descriptions to the selection UIs:
  - `backend/routers/catalog.py`: catalog summary and detail now
    include a `description` field, from the config's `description`
    or derived from the persona backstory / system prompt.
  - Runner, Eval, and Chatter show the selected agent's description
    beneath the picker so users see what each agent does.
  - `backend/tests/test_catalog.py`: tests for `_description` and
    `_first_sentences`.


### v0.22.4 - 12th July 2026

- Fixed the Runner's Single tab for agents whose input is a single
  free-text string (e.g. `CompanyPersonExtractor`, classifiers):
  - Updated `frontend/src/pages/Runner.svelte`: detect string vs
    dict example input and render one text area for string agents,
    instead of spreading the example string into one box per
    character via `Object.entries`.
  - Updated `backend/routers/run.py`: route scalar `input_data`
    through `act_in_batch` (as eval does) since the framework's
    single `act()` only accepts a dict; a bare string previously
    raised `AgentConfigurationError`.
  - Added `backend/tests/test_run.py`: cover dict→`act`,
    scalar→`act_in_batch`, and empty-batch parse-error routing.


### v0.22.3 - 12th July 2026

- Updated `frontend/src/components/Sidebar.svelte`: shortened the
  default sidebar width from 336px to 300px.


### v0.22.2 - 12th July 2026

- Updated `frontend/src/components/Sidebar.svelte`: dropped the
  `· console` tagline from the brand subtitle — it now shows only the
  version (`v{version}`).


### v0.22.1 - 12th July 2026

- Updated `frontend/src/components/Sidebar.svelte`: raised the default
  sidebar width 1.4× (240px → 336px) so it opens wider by default;
  still user-adjustable and within the 180–420px clamp.


### v0.22.0 - 12th July 2026

- Updated `frontend/src/components/Sidebar.svelte`:
  - Made the sidebar width adjustable by dragging its right edge; the
    chosen width is clamped (180–420px) and persisted in
    `localStorage` across sessions.
  - Added keyboard resizing on the focusable handle (arrow keys to
    nudge, Shift for larger steps, Home/End for min/max) and
    double-click to reset to the default width.
  - Raised `.brand-sub` from `0.8125rem` to `1.0625rem` to meet the
    17px raw-text floor, and nudged `.brand-name` to `1.3rem` to keep
    the name/subtitle hierarchy.


### v0.21.1 - 11th July 2026

- De-conflicted the dev backend host port from the shared `8001` to a
  registry-claimed `8002`, so `pnpm dev` no longer proxies `/api` into a
  leftover backend from another project (market_wrapper also binds
  8001):
  - Updated `frontend/vite.config.js`: proxy target `/api` → `:8002`.
  - Updated `README.md`: backend run command and proxy notes use `8002`.


### v0.21.0 - 11th July 2026

- Reworked the frontend navigation from a top header bar to a lateral
  sidebar menu, mirroring the market_wrapper console style:
  - Added `frontend/src/components/Sidebar.svelte`: lateral menu with a
    brand mark, app name + version subtitle, icon-per-item nav (Home,
    Catalog, Runner, Chatter, Engine, Eval) with an accent active state,
    and the Ollama engine status pill + Start button pinned at the base.
  - Updated `frontend/src/App.svelte`: full-height sidebar + scrollable
    content shell; fetches `/api/info` and passes name/version to the
    sidebar. Kept hash routing, page switching, and Ollama start logic.
  - Updated `frontend/src/app.css`: `#app` is now a full-height row
    layout; added slim custom scrollbars.
  - Updated `frontend/src/pages/Home.svelte`: removed the intro version
    badge now that the sidebar shows name + version in persistent chrome.


### v0.20.8 - 11th July 2026

- Updated `docker-compose.yml`:
  - Exposed the FastAPI backend on a registry-claimed host port
    (`${API_PORT:-5191}` → container 8000), so the backend API and its
    Swagger UI (`/docs`) are reachable directly, not only same-origin
    via nginx.
  - Expanded the `banner` service to advertise the Backend and Swagger
    URLs alongside the App URL.
- Updated `agents7_ui/.env.example`: documented `API_PORT`.


### v0.20.7 - 11th July 2026

- Updated `docker-compose.yml`:
  - Replaced the frontend `post_start` echo with a dedicated `banner`
    busybox service, matching the fleet-canonical startup-banner format
    (blank-line padded, `➜`-prefixed, reads the same `${FRONTEND_PORT}`
    the ports mapping binds).


### v0.20.6 - 11th July 2026

- Updated `.env.example`: added the external OpenAI-compatible provider vars (`OPENAI_COMPAT_MODEL_NAME`, `OPENAI_COMPAT_BASE_URL`, `OPENAI_COMPAT_API_KEY`) to the LLM provider keys section, for pointing an `openai_compat` agent at a provider like DeepSeek.


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
