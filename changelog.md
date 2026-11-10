
## Changelog - agents7 UI


### v0.49.7 - 10th November 2026

- Rotated changelog: archived 11 entries to `changelog/2026.md`.


### v0.49.6 - 8th November 2026

- Updated `.claude/rules/00-rule-index.md`: regenerated, it now lists
  `metrics-completeness`.


### v0.49.5 - 7th November 2026

- `backend/uv.lock`: framework tag `v9.25.9` re-resolved to commit
  `bb03025`. The framework's history was rewritten and its repository
  recreated, so the tag names a new commit; the code under it only
  changed in docstrings, tests and the guard prompt's examples.


### v0.49.4 - 7th November 2026

- Fixed `backend/routers/chat.py` `save_as_read`: for an agent found
  only as an installed package (outside `CATALOG_PATH`), the read was
  written into the installed package and then answered with a server
  error. It is now refused before anything is written, with a message
  saying to point `CATALOG_PATH` at the agent's checkout.
- `backend/tests/test_chat_save_read.py`: regression test for it.
- `docs/reads.md`: says which agents can be saved.


### v0.49.3 - 7th November 2026

- `README.md`: three screenshots, in `docs/screenshots/`: the Catalog,
  a Chatter conversation and an Eval run. Taken with the framework's
  public samples and the public sentiment classifier, with real model
  calls on Ollama.
- `backlog.md`: two display issues seen while taking them.


### v0.49.2 - 7th November 2026

- `README.md` is a short overview (104 lines, was 211): what the UI does,
  which agents it shows, running it locally and with Compose,
  configuration, tests and logs.
- Added `docs/reads.md`: the Reads page in detail, moved from the README.
- `.claude/rules/committing.md`: user-facing changes go in `docs/`; the
  README stays an overview (owner, 7th November 2026).
- `backend/routers/catalog.py`: a comment pointed at a framework page
  that no longer exists; it now names `docs/agent-packages.md`.


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
