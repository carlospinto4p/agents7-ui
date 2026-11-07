
## Changelog - agents7 UI


### v0.49.1 - 7th November 2026

- `README.md`: the example agent installs from its renamed repository,
  `agent-sentiment_classifier`, tag `v0.1.1`.


### v0.49.0 - 7th November 2026

- `backend/routers/catalog.py`: the catalog also lists agent packages
  installed in the backend's environment, found through the
  `agents7.agents` entry point group (`ENTRY_POINT_GROUP`), after the
  `CATALOG_PATH` folder's configs. A config found both ways is listed
  once; an entry point that fails to load or names a missing file is
  logged and skipped. Run, Eval and Chat find these agents by name like
  any other. Step 3 of the framework's `docs/repository-split.md`.
- `backend/tests/test_catalog.py`: 5 tests for installed agents.
- `README.md`: how to install an agent package beside the UI.


### v0.48.1 - 7th November 2026

- Added the project's Claude Code setup, carried over from the old
  combined repository and cleaned for a public repository:
  - `CLAUDE.md`: written for the UI, with the old file's general rules
    kept as they were.
  - `.claude/rules/`: committing, versioning, testing, the review-area
    notes (with the Svelte `$effect` notes), `metrics-completeness.md`
    (triggered by `backend/` and `frontend/src/`), and a rule index.
  - `.claude/skills/fix-errors/` and its `.opencode/` command, with
    paths at the repository root.
  - `.claude/settings.json`: tool permissions.
- Added the pre-commit setup: `.pre-commit-config.yaml` (ruff pinned to
  v0.15.9, changelog and version guards) and `.pre-commit-scripts/`;
  `pre-commit` joins the backend's dev dependencies so the hook has a
  stable environment.
- Added `scripts/changelog-add.sh`.


### v0.48.0 - 7th November 2026

- The UI is now its own repository, cut from the old combined one with
  its history (the stretch from 24th August to 7th November 2026 is
  one squashed commit). The repository root is the old `agents7_ui/`
  folder, plus `docker-compose.yml`.
- The framework is a tagged release instead of a sibling folder:
  - `backend/pyproject.toml`: `agents7` comes from
    `github.com/carlospinto4p/agents7` at tag `v9.25.9`.
  - `Dockerfile.backend`: installs the same tag (`AGENTS7_TAG`)
    instead of copying the framework's source; build context is the
    repository root.
  - `backend/main.py`: `/api/readme` serves the installed package's
    README instead of reading a sibling file, and answers `404` when
    the package is missing.
- The UI ships no agents. The default catalog is the repository's
  git-ignored `catalog/` folder instead of the old `samples/`;
  `CATALOG_PATH` still overrides it, and Compose mounts `catalog/`
  read-only at `/app/catalog`.
- Updated every path that assumed the `agents7_ui/` folder:
  `docker-compose.yml`, `scripts/install_catalog.py`, the install hint
  in `routers/utils.py`, `.env.example`, `README.md`, `env_setup.py`.
- Added `LICENSE` (MIT) and `ruff.toml`; `.dockerignore` and
  `.gitignore` cover the new layout.
- `tests/test_security.py`: the README tests read package metadata,
  and a new test checks the `404`.


### v0.47.3 - 7th November 2026

- Root `CLAUDE.md`: the framework moved to its own repository, checked
  out at `../framework`; `agents7_framework/` here is frozen, and the UI
  keeps using it until it is split off too.


### v0.47.2 - 7th November 2026

- Rotated changelog: archived 3 entries to `changelog/2026.md`.


### v0.47.1 - 7th November 2026

- Reworded examples ahead of publishing this repository: backend
  tests, Playwright specs and docstrings use the sample persona David
  and neutral mock names (`my_tagger`); the feedback form's
  placeholder names `characters/david.yml`; `changelog.md` and
  `changelog/2026.md` reword 9 passages. Behaviour is unchanged.


### v0.47.0 - 7th November 2026

- The UI serves the repository's `samples/` by default, since the
  agent catalog moved to its own repository:
  - `routers/catalog.py`, `routers/reads.py`: `CATALOG_PATH` defaults to
    `samples/`. Point it at a catalog of your own to serve its agents.
  - `scripts/install_catalog.py`: reads the catalog from `CATALOG_PATH`
    too, defaulting to `samples/`, which needs nothing installed.
  - `Dockerfile.backend`: copies only `samples/` and no longer installs
    catalog packages, so the Compose stack serves the samples alone.
  - `README.md`, `.env.example`: say how to serve your own catalog.


### v0.46.1 - 7th October 2026

- Rotated changelog: archived 3 entries to `changelog/2026.md`.


### v0.46.0 - 4th October 2026

- Updated the block above a read's conversation that says what it
  ran with, in `frontend/src/components/ReadConversation.svelte`:
  - One titled section per group: Run, Context, Knew already,
    Variants. Needs agents7 v9.25.0; rows with no group fall into one
    untitled section.
  - Each label sits above its value instead of beside it.
  - A value over 48 characters, and every variant, takes the whole
    width of its section.
  - The facts the agent already knew are a list in columns.
- Added `e2e/reads-context.spec.js`: 4 tests.


### v0.45.2 - 4th October 2026

- Fixed prose stopping at about half the page while the cards and
  tables beside it ran the full column. Removed the `max-width` from
  text blocks in `frontend/src/pages/`:
  - `Reads.svelte`: `.standfirst`, `.caveat`, `.nospec`, `.closing`.
  - `Runner.svelte`: `.page-intro`, `.agent-desc`.
  - `Eval.svelte`: `.intro-desc`, `.agent-desc`.
  - `Catalog.svelte`: `.intro-desc`, `.detail-desc`.
  - `Home.svelte`, `Engine.svelte`, `Classes.svelte`: `.intro-desc`.
  - `Chatter.svelte`: `.agent-description`.
- Added `e2e/reads-text-width.spec.js`: the read's standfirst, caveat
  and closing are as wide as a verdict card at 1920px.


### v0.45.1 - 4th October 2026

- Rotated changelog: archived 6 entries to `changelog/2026.md`.


### v0.45.0 - 2nd October 2026

- Added a narrow-viewport layout: at 640px wide or less the sidebar
  becomes an icon rail, so the page keeps the rest of the width.
  - `frontend/src/components/Sidebar.svelte`: the rail hides the
    labels, the brand text and the resize handle. Each link keeps
    its name through `aria-label` and `title`, and the stored
    sidebar width is left alone.
  - `frontend/src/App.svelte`: smaller content padding at that
    width.
  - `frontend/e2e/sidebar.spec.js`: 3 tests.


### v0.44.0 - 2nd October 2026

- Added support for a context value computed from another one, so
  a Chatter conversation with a chat agent gets a value worked out
  from another field instead of running with it blank.
  - `backend/routers/catalog.py`: `_context_params` reports
    `derived_from` for each declared value.
  - `frontend/src/pages/Chatter.svelte`: a derived value gets a
    line saying which field it is worked out from, and no field.
  - `backend/pyproject.toml`: agents7 floor raised to 9.21.0, the
    version that computes it.
- Added tests:
  - `backend/tests/test_catalog.py`: 1 test.
  - `backend/tests/test_chat.py`: 1 test.
  - `frontend/e2e/chatter-context.spec.js`: 1 test.


### v0.43.0 - 2nd October 2026

- Added a link from a saved conversation to the Reads page, and an
  address for a read, so reviewing what was just saved is one click
  and not a hop to the other page and a pick from the dropdown.
  - `frontend/src/components/ChatPanel.svelte`: the "Saved N turns"
    confirmation ends in an "open it on the Reads page" link. A
    failed save shows none.
  - `frontend/src/pages/Reads.svelte`:
    - `?read=<path>` in the hash selects a read; an unknown path
      falls back to the first one.
    - `&conv=<id>` opens a conversation by its recording's name. It
      applies to the first load only.
    - The hash is rewritten with the current read whenever the tab
      or the read changes.
  - `frontend/src/App.svelte`: the page name no longer includes a
    query after it.
  - Added `e2e/reads-link.spec.js`: 6 tests.
  - `e2e/chatter-save-read.spec.js`: 2 tests for the link.
- Updated `README.md`: the link and the address format.
- Updated `backlog.md`: removed the item this closes.


### v0.42.0 - 2nd October 2026

- Added markers on the Reads page for what already carries feedback,
  so it shows without scrolling to each turn. Both are part of Review
  mode and absent in Read mode.
  - `frontend/src/components/ReadConversation.svelte`: a strip of
    turn numbers above the thread, headed "Feedback on N of M turns".
    A turn with feedback is filled; clicking a number scrolls to that
    turn and focuses its `+ Feedback` button.
  - `frontend/src/pages/Reads.svelte`: each conversation's tab shows
    a count of its entries, whole-conversation notes included. No
    count is shown at zero.
  - Added `e2e/reads-feedback-markers.spec.js`: 5 tests.


### v0.41.0 - 2nd October 2026

- Added a keyboard path to the Reads page's feedback form, so a read
  can be judged turn after turn without the mouse.
  - `frontend/src/components/FeedbackForm.svelte`:
    - Opens with the caret in "Should say".
    - ctrl+enter (or cmd+enter) saves from any field.
    - Escape cancels.
    - Now a `<form>` labelled "Feedback", with a line naming the two
      keys beside its buttons.
  - `frontend/src/components/ReadConversation.svelte`:
    - Saving moves focus to the next turn's `+ Feedback` button.
    - Cancelling and deleting return focus to the same turn's button.
    - Arrow up and down step between the turns' buttons.
  - Added e2e tests, the first for the Reads page:
    - `e2e/reads-feedback-keyboard.spec.js`: 5 tests.
    - `e2e/_reads.js`: a stubbed read shared by Reads specs.


### v0.40.1 - 22nd September 2026

- Rotated changelog: archived 3 entries to `changelog/2026.md`.


### v0.40.0 - 20th September 2026

- Added **Save as read** to the Chatter page, joining the two halves
  of the UI. A conversation held here was answered and forgotten: the
  Reads page could only show what a script had recorded, so feeding
  back on a chat meant leaving the UI to record it again — and at
  temperature, running it again is a different conversation, so it
  could never be the same one.
  - `backend/routers/chat.py`:
    - `_Transcript`: accumulates a session into the framework's
      `Recording` shape. Built by recording at the point each
      endpoint has its reply rather than by driving the session
      through `ConversationRecorder`, which replaces the
      `guard_callback` this router needs for its metrics line and
      has no async or streaming path — and three of the four ways a
      turn arrives here are one or the other.
    - `_GuardCollector` keeps whole guard events, not just their
      cost, so a saved read carries why a reply was rejected and
      what was suggested instead. `summary()` is unchanged.
    - `POST /api/chat/{session_id}/save-read`: writes the recording
      under the agent's own `docs/reads/<read_id>/`. A snapshot
      rather than an ending — the session stays open, so a
      conversation can be saved and then continued. An existing file
      is refused with a 409: a recording is paid for and is never
      overwritten.
    - `_package_version`: reads the agent package's `pyproject.toml`
      rather than `Chatter.version`, which is the config *schema*
      version — a recording came out stamped `1` that way once.
    - Read ids and conversation ids are restricted to characters
      that cannot escape a directory.
  - `frontend/src/components/ChatPanel.svelte`: the control, with the
    read and conversation names editable and today's date offered.
    The Download button beside it still writes `{role, text}`, which
    no read can use — this writes what the Reads page reads.
- Added tests:
  - `backend/tests/test_chat_save_read.py`: 26 covering the package
    lookup, the collector keeping verdicts, turn recording across
    the four paths, and the save endpoint's refusals.
  - `frontend/e2e/chatter-save-read.spec.js`: 9 covering the
    control's absence before anything is said, the form, the request
    it sends, a name collision and an empty name.


### v0.39.0 - 20th September 2026

- Added the **Reads** page: read a chat agent's recorded
  conversations, and attach feedback to a turn. Judging a read has
  until now meant a text editor — holding turn numbers in your head
  and typing `turn: 7` by hand — and that is the slow half.
  - `frontend/src/pages/Reads.svelte`: the read picker, the
    Read / Review toggle, the tab bar (Verdicts, Numbers, one per
    conversation, Feedback), verdict cards with their three stamps,
    the numbers table with its comparison column, and the derived
    feedback report with copy and download. The tab lives in the
    hash — `#/reads/conv-1` — so one conversation can be linked to,
    the way the generated page's `read.html#conv-1` can.
  - `frontend/src/components/ReadConversation.svelte`: one
    conversation as a chat client — agent left, counterpart right, a
    multi-line reply split into one bubble per line — with the
    context block, the per-turn metrics line (agent, guard, gap,
    total, cost split into its two halves, running total, tokens and
    cached share), the guard-attempts disclosure, and the notes from
    the read spec in their four colours.
  - `frontend/src/components/FeedbackForm.svelte`: the form that
    attaches one correction, pre-filled with `he_said` from the
    reply so a rewrite cannot drift from the line it corrects. Its
    fields are one-shot seeds rather than bindings, so a re-render
    never overwrites what is being typed; the caller remounts it
    when a different entry is opened.
  - `backend/routers/reads.py`: discovers read folders under the
    catalog, serves the framework's own `read_payload` rather than
    rebuilding it, and writes feedback to the same `feedback.yml`
    the `chat-feedback` command reads. Never a second store: a read
    half in a database and half in git would be worse than the
    editor it replaces.
- Added `backend/tests/test_reads.py`: 24 tests covering discovery,
  catalog-escape refusal, serving a folder that has no `read.yml`,
  and the merge semantics — including `clear`, which is what makes
  deleting the last entry on a turn possible, since merging keys on
  the turns the incoming entries name.
- Updated `backend/pyproject.toml`: `agents7>=9.19.0`, the second
  feature requirement this backend has ever had. `read_payload`,
  `eval.chat_feedback` and `Recording.context` do not exist earlier,
  so the router's imports fail outright rather than degrading.


### v0.38.4 - 7th September 2026

- Rotated changelog: archived 3 entries to `changelog/2026.md`.


### v0.38.3 - 6th September 2026

- Updated `backend/routers/utils.py`:
  - `_load_config` returns the *resolved* configuration, so an
    agent whose persona lives in a `character` file and whose scene
    lives in a `chat_goal` file still lists with a display name and
    still renders its persona and scene panels. One catalog agent is
    the first split that way; before this it would have listed under
    its bare name with both panels empty.
  - A config the framework refuses falls back to a plain parse, so
    one broken agent cannot empty the catalog.
  - The raw YAML shown on the detail page is still the authored
    file, which is the one to edit.
- Updated `backend/pyproject.toml`: the `agents7` floor is
  `>=8.5.0`, the version that resolves the composition.


### v0.38.2 - 5th September 2026

- Updated `backend/pyproject.toml`:
  - Raised the `agents7` floor from `>=5.0.0` to `>=8.0.1`, the
    version the UI is developed and tested against. The lock
    recorded 5.4.0 against a source tree three majors ahead, which
    misinformed a reader about what the backend runs. Nothing was
    broken: the dependency is an editable path install, so the venv
    always ran what was on disk, and the v6, v7 and v8 majors are
    confined to `eval.style` and `eval.style_history`, which this
    backend does not import.
- Updated `backend/uv.lock`: records `agents7` at 8.0.1.


### v0.38.1 - 4th September 2026

- Rotated changelog: archived 3 entries to `changelog/2026.md`.


### v0.38.0 - 3rd September 2026

- Updated `backend/routers/run.py`:
  - `_step_payload()` sends a tool step's `error` alongside its
    `result`. Both are needed: `result` is the `"Error: ..."` text
    the model was handed, and `error` is what says the call failed
    — a tool may legitimately return text beginning with `Error:`,
    which is why agents7 v5.0.0 made failure its own field.
- Updated `frontend/src/pages/`:
  - `Runner.svelte`, `Catalog.svelte`: a call the tool rejected is
    marked. The card takes the fail border, the header gains a
    `rejected` badge, and the block is labelled `Error` rather than
    `Result` with the failure colours. Previously it rendered in
    the same `tool-result` block as a successful call, so a reader
    had to infer the failure from the text.
  - `Eval.svelte`: the trajectory line reports `failed_calls` as
    `N rejected`, so a matched/expected gap says what closed it.
- Updated tests:
  - `backend/tests/test_run.py`: a rejected call's payload carries
    `error`; a successful one omits it.
  - `frontend/e2e/tool-agent-run.spec.js`,
    `tool-agent-catalog.spec.js`: a rejected call is marked on both
    pages, and a successful one is not.
  - `frontend/e2e/tool-agent-eval.spec.js`: the rejected count is
    rendered.
- Updated `backend/pyproject.toml`: requires agents7 >= 5.0.0.


### v0.37.0 - 3rd September 2026

- Updated `backend/routers/eval.py`:
  - Every agent type now goes through `agents7.eval.run_eval_suite`.
    Only a tool agent did; every other type ran a hand-rolled loop
    that duplicated `run_evaluation` and `compute_metrics`, and had
    drifted from the framework's own field comparison — a missing
    key was compared as `""` where the framework matches `None`
    against `None`.
  - The response carries what that duplication had been discarding:
    `per_field` accuracy, `timing`, `per_category` from the
    framework, `calls` (the run's call totals, tokens, duration and
    cost), the resolved `model`, and `error` on a row the agent
    never answered.
  - Dropped the endpoint's own `agent_type` check; the framework
    rejects an unknown type and the endpoint relays it as a 422.
- Updated `frontend/src/pages/Eval.svelte`:
  - Added a per-field accuracy table, worst field first.
  - Added a line reporting what the run cost — calls, tokens, time
    (with the average and spread when there was more than one call),
    money, cache hits and retries. An Ollama run reads `unpriced`
    rather than `$0.00`.
  - A mismatch the agent never answered shows its error instead of
    an empty `Actual`, and the summary counts those rows apart from
    the wrong answers.
- Added `frontend/e2e/tool-agent-eval.spec.js` specs for the
  per-field table, the cost line, an unpriced run, a single-call
  run, and the failed-call row.
- Requires agents7 v4.38.1.


### v0.36.1 - 31st August 2026

- Rotated changelog: archived 7 entries to `changelog/2026.md`.


### v0.36.0 - 29th August 2026

- Added retries to what a turn and a run report, from agents7
  v4.26.0. A response that fought the provider took several
  attempts and several times as long, and nothing on screen said
  so — the duration beside it is the successful attempt's own
  figure, so the wait was invisible.
  - `frontend/src/lib/format.js`: added `retryLabel()`, rendering
    `2 retries (4.5s)`. The seconds are in brackets rather than
    written as `+4.5s` because whether they are already inside the
    duration next to them depends on the page: the Chatter shows
    the framework's `total_duration`, which excludes them, while
    the Runner and Catalog show a stopwatch that was ticking
    throughout. For a guarded turn the guard's retries are added
    in, since both halves held the same person up.
  - `metricsLine()` and `stepMetaLine()` end in the retry part
    when there is one, and are unchanged when there is not.
  - `frontend/src/pages/Runner.svelte` and `Catalog.svelte`: the
    run-level meta line, which each build by hand, says it too.
- Updated the metrics payloads to mirror the framework structurally
  rather than by hand:
  - `backend/routers/chat.py` and `run.py`: both dump `LLMMetrics`
    instead of listing its fields, and `_NO_METRICS` is the model's
    own zero. Listing the fields is how these payloads fell behind
    twice, on `cached` and on `cached_prompt_tokens`.
  - `backend/routers/chat.py`: `_GuardCollector.summary()` and
    `run.py`'s pipeline total now add with `LLMMetrics.sum`, the
    framework's one aggregator, instead of summing field by field.
    A pipeline whose every step was a cache hit on a priced engine
    now reads as `0.0` rather than as unpriced, which is the
    honest answer — it really did spend nothing.
- Fixed the engine override dropping the agent's pricing:
  - `backend/routers/chat.py`: `pricing` is kept when the override
    names the agent's own provider *and* model. It was dropped on
    every override, so choosing the very model the rates were
    written for left the turn unpriced and its cost silently
    absent from the page. A different model still drops them —
    rates belong to one model, and carrying them would put a
    confident price on a turn never billed at them.
- Added tests:
  - `backend/tests/test_chat.py`: retries in the payload and in
    the guard summary, the three pricing-override cases, and the
    metric stubs rebuilt on the real `LLMMetrics` so a field added
    upstream cannot leave them behind.
  - `backend/tests/test_run.py`: retries in a run's payload; the
    two hand-written expected dicts replaced by comparisons
    against the framework's own model.
  - `frontend/e2e/chatter-retries.spec.js`: 4 cases over the
    rendered line.


### v0.35.0 - 29th August 2026

- Added the response cache to what a turn reports:
  - `backend/routers/chat.py`: the metrics payload carries `cached`,
    and the guard summary carries `cached` and
    `cached_prompt_tokens`.
  - `backend/routers/run.py`: added `_metrics_payload()` and
    `_NO_METRICS`, replacing six hand-built dicts — three had
    drifted and were missing `cached_prompt_tokens`.
  - `frontend/src/lib/format.js`: added `cacheLabel()` and
    `stepMetaLine()`. The metrics line ends in `cached`, or `reply
    cached` when the guard really ran.
  - `frontend/src/pages/Runner.svelte` and `Catalog.svelte`: the
    run and per-step meta lines say when a result came from cache.
- Added tests:
  - `backend/tests/test_chat.py`: the payload carries a cache hit;
    the guard summary reports its own cache state.
  - `backend/tests/test_run.py`: run metrics carry the flag; a run
    that produced nothing is unpriced, not free. The metric stubs
    now use the real `LLMMetrics` so a new field cannot leave them
    behind.
  - `frontend/e2e/chatter-cached.spec.js`: 4 cases over the
    rendered line.
- Updated `.claude/rules/metrics-completeness.md`: moved the
  UI cache gap into the closed list.


### v0.34.0 - 29th August 2026

- Updated `backend/routers/chat.py` to report the guard's own
  cost beside the reply's:
  - Added `_GuardCollector`, attached to a guarded chatter when
    its session starts and reset at the top of every turn, since
    the framework's callback fires once per guard attempt.
  - `_metrics_dict` now carries a `guard` object (`calls`,
    `tokens`, `prompt_tokens`, `total_duration`, `cost_cents`)
    and a `total_cost_cents`, plus `cached_prompt_tokens` from
    agents7 v4.21.0.
  - Applies to `send_message`, `open_turn` and both streaming
    routes.
- Updated `frontend/src/lib/format.js`:
  - `fmtCost` formats three significant digits with trailing
    zeros stripped, instead of a fixed four decimal places of
    dollars.
  - `metricsLine` renders a guarded turn as
    `29 tok · 1.9s · $0.000168 + guard $0.000146 = $0.000314`.
    An agent with no guard, or one with no pricing, is unchanged.
- Added tests:
  - `backend/tests/test_chat.py`: 8 tests covering attachment,
    per-attempt summing, the per-turn reset, and the unguarded
    and unpriced cases.
  - `frontend/e2e/chatter-cost.spec.js`: 4 tests on the rendered
    line.

**Two bugs, both of which made the number wrong rather than
imprecise.** A guarded reply is at least two LLM calls and only
the first is in the `ChatResponse`, so the page showed about half
of what a turn cost — measured on a chat agent, the guard is 46% of
the bill. And a real $0.000168 rounded to `$0.0002`, while
anything under $0.00005 rendered as `$0.0000`, a price that reads
as free.


### v0.33.5 - 28th August 2026

- Fixed `Dockerfile.backend`: the framework is now installed as
  `agents7[anthropic,openai]`, matching what
  `backend/pyproject.toml` already declared. The image installed
  it with no extras, so building an Anthropic or `openai_compat`
  engine raised `ImportError` in Compose while working locally.
  Surfaced by a catalog chat agent, which runs on DeepSeek
  through `openai_compat` and so is the first packaged agent that
  needs the extra at run time.
- Updated `backend/tests/test_chat.py`: the fixture docstring
  naming the catalog agent that records character facts now uses
  that agent's new name. It was a sample under
  `agents_catalog/examples/`; it is now a released package at the
  catalog root. The Catalog page needs no change — it tiers an
  agent by whether `examples` is in its path, so the agent moved
  from the sample list to the agent list on its own, and
  `scripts/install_catalog.py` picks the package up by discovery.


### v0.33.4 - 28th August 2026

- Added `frontend/e2e/`:
  - `chatter-error.spec.js`: six specs pushing the backend's
    `event: error` frame over the stubbed chat stream, covering the
    message rendering above the transcript, the empty bubble being
    dropped when a turn fails before speaking, partial text being kept
    when it fails mid-sentence, the fallback message for a frame
    carrying none, the opening turn failing the same way, and the next
    message clearing the previous failure.


### v0.33.3 - 28th August 2026

- Updated `backend/routers/chat.py`: catch provider errors, not just
  framework ones. The four chat-turn handlers caught only
  `Agents7Exception`, so an error raised by a provider SDK — a revoked
  key, a rate limit, a model the account cannot reach, an endpoint that
  is down — escaped them. The non-streaming routes then answered 500
  with a traceback instead of the generic detail beside them, and
  `_stream_turn` broke the Server-Sent Events stream instead of
  emitting the `event: error` frame the frontend renders. All four now
  catch `Exception`, keeping the logging and the generic response body.
- Added tests in `backend/tests/test_chat.py`:
  - `_ProviderErrChatter`: a chatter that fails the way a provider SDK
    does, through a type that is not an `Agents7Exception`.
  - Provider-error regression tests for `send_message`, `open_turn`,
    `remember_turn`, `stream_message` and `stream_opening`.
  - First tests for `send_message`, which had none: unknown session,
    missing message, the reply and its metrics, and a framework error.


### v0.33.2 - 28th August 2026

- Rotated changelog: archived 5 entries to `changelog/2026.md`.


### v0.33.1 - 27th August 2026

- Updated `backend/routers/`:
  - `utils.agent_unavailable()`: builds a 422 naming the module that
    could not be imported and the command that reinstalls it.
  - `run.py`: `POST /api/run/<agent>` answers 422 instead of 500 when
    the agent's own package is missing, on both the structured and
    the tool route.
  - `eval.py`: same for `POST /api/eval/<agent>`, on both routes.
- Added tests:
  - `tests/test_utils.py`: 2 tests for the message.
  - `tests/test_run.py`: 2 tests for the run routes.
  - `tests/test_eval.py`: 2 tests for the eval routes.
- Updated `backend/pyproject.toml`: recorded why catalog agents are
  not backend dependencies — each is an independent package, so the
  UI never enumerates them.
- Updated `README.md`: the catalog-install step now says a missing
  package is reported, not a traceback.
