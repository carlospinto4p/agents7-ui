
## Changelog - agents7 UI


### v0.29.5 - 23rd August 2026

- Fixed `frontend/src/pages/Catalog.svelte`: the backend already
  returned each agent's `description` (from its `config.yml`), but
  the Catalog page never rendered it. Added a clamped description
  line to each grid card and the full description to the agent
  detail header.


### v0.29.4 - 23rd August 2026

- Fixed `backend/main.py`: the framework README path used
  `Path(__file__).parents[1]`, resolving to a nonexistent
  `agents7_ui/agents7_framework/README.md` and 404ing the Home
  page's README fetch. Corrected to `parents[2]` to reach the
  repo-root `agents7_framework/README.md`.


### v0.29.3 - 28th July 2026

- Rotated changelog: archived 2 entries to `changelog/2026.md`.


### v0.29.2 - 26th July 2026

- Redeployed the hardened `scripts/changelog-add.sh`: guards against
  the CWD-relative wrong-repo footgun (comparing the target
  changelog's version against the wrong repo's manifest when invoked
  from outside its own directory).


### v0.29.1 - 19th July 2026

- Rotated changelog: archived 7 entries to `changelog/2026.md`.


### v0.29.0 - 18th July 2026

- Added tool-agent support to the eval endpoint:
  - `backend/routers/eval.py`: scores a `tool` agent by delegating to
    `agents7.eval.run_eval_suite`, returning the framework's
    `trajectory` metrics plus the calls each failed row made, missed
    and added.
  - `_find_golden_set()`: falls back to an `eval_data.jsonl` beside
    the config, so a tool agent's trajectory set is discovered.
    Agents shipping `data/golden_set.*` are unaffected.
  - Removed `reject_tool_agent()` from `backend/routers/utils.py` —
    both endpoints it guarded now serve tool agents.
- Added the trajectory view to the Eval page:
  - `frontend/src/pages/Eval.svelte`: renders match mode, call
    totals, and per-tool recall in place of the per-category table,
    and lists called/missing/extra calls per mismatch.
- Added tests:
  - `backend/tests/test_eval.py`: 10 tests covering eval-set
    discovery and the trajectory route.
  - `frontend/e2e/tool-agent-eval.spec.js`: 3 e2e tests.


### v0.28.0 - 18th July 2026

- Added tool-agent support to the run endpoint:
  - `backend/routers/run.py`: runs a `tool` agent through
    `act_stream`, returning its free-text `answer` plus the
    `tool_steps` trajectory. An exhausted loop reports its `error`
    and the calls it made instead of failing the request.
  - Removed the `reject_tool_agent` guard from the run path.
- Added the tool-agent view to the Runner page:
  - `frontend/src/pages/Runner.svelte`: renders the answer and pairs
    each tool call with the result that answered it. A tool agent now
    falls back to a free-text input when it declares no
    `system_examples`.
  - `frontend/src/constants.js`: added `isToolAgent()`.
- Added tests:
  - `backend/tests/test_run.py`: 4 tool-agent tests.
  - `frontend/e2e/tool-agent-run.spec.js`: 3 e2e tests.


### v0.27.1 - 18th July 2026

- Updated `backend/routers/`:
  - `utils.py`: added `reject_tool_agent()`. `tool` joined the
    framework's `AGENT_TYPE_MAP` in agents7 v4.14.0, so it now passes
    the membership check the run and eval endpoints share; neither can
    serve it (both read `response.model`, which a `ToolAgent` never
    populates), so they refuse it with a 422 pointing at the CLI
    instead of returning an empty output.
  - `run.py`, `eval.py`: call the guard.
- Added `backend/tests/test_utils.py` coverage for the guard: 2 tests.


### v0.27.0 - 18th July 2026

- Added a Playwright end-to-end test harness in `frontend/`:
  - `playwright.config.js`: pins the dev server to the claimed port
    5186 and starts it via `webServer`, reusing a running one locally.
  - `e2e/_helpers.js`: stubs every `/api` boundary, so specs need no
    backend. Catch-all registered first, specific endpoints last.
  - `e2e/sidebar.spec.js`: 7 tests covering drag-to-resize, the
    min/max clamps, double-click reset, keyboard nudging, and width
    persistence across a reload (v0.22.0).
  - `e2e/chatter-override.spec.js`: 7 tests covering the engine
    override, including the regression test owed for the v0.26.3 fix
    — both branches, Ollama with no installed models (blocked) and
    `openai_compat` whose model comes from the environment (allowed).
  - `test:e2e` script and the `@playwright/test` dev dependency.
- Updated `.gitignore`: ignore `frontend/test-results/` and
  `frontend/playwright-report/`.


### v0.26.3 - 18th July 2026

- Fixed the **Chatter** page starting a session with an engine override
  that has no model, which failed server-side as a 400 and logged a
  warning:
  - `frontend/src/pages/Chatter.svelte`: new `needsModel` derived flag —
    true when a provider is selected, no model is set, and the provider
    does not supply one itself. `onProviderChange()` leaves `ovModel`
    empty whenever Ollama reports no installed models (or has not
    answered yet), and nothing downstream re-checked it.
  - While `needsModel` holds, `ChatPanel` is not mounted and the page
    explains what is missing, instead of handing the backend an
    override it will reject.
  - `openai_compat` is unaffected: its model may legitimately come from
    the environment, which `/api/chat/providers` reports as `model`.


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
