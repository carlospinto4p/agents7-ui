# agents7 UI

Web UI for the [agents7](https://github.com/carlospinto4p/agents7)
framework: browse agents, run them,
chat, evaluate, read back recorded conversations, and inspect the
Ollama engine. FastAPI backend + Svelte (Vite) frontend.

The **Reads** page is the one that writes rather than only showing.
It finds every read folder under the catalog — an agent's
`docs/reads/<date>/` holding recordings written by
`ConversationRecorder` — renders each conversation as a chat, and
lets a correction be attached to any turn. Above the chat a block
says what the conversation ran with, in four sections: the run, the
context it was given, what the agent already knew, and the prompt
variants it drew. The feedback form works
from the keyboard: it opens with the caret in its first field,
ctrl+enter saves from any field and moves to the next turn's button,
escape cancels, and arrow up and down step between the turns'
buttons. What has been judged shows without scrolling: each
conversation's tab carries a count of its entries, and a strip of
turn numbers above the thread fills in the turns that have feedback
and jumps to one when clicked.

Conversations get there from either side. A script can record one
(`ConversationRecorder`), or you can hold one on the **Chatter**
page and press **Save as read**, which writes the same recording
under that agent's `docs/reads/`. The Download button beside it is
a different thing: it writes `{role, text}` for reading elsewhere,
with no metrics, guard verdicts or context, so no read can be built
from it. Saving leaves the session open, so a conversation can be
saved and then continued, and an existing recording is never
overwritten. The confirmation links straight to the saved
conversation on the Reads page.

A read has an address. `#/reads/conv-1?read=<path>` opens the read
at `<path>` (relative to the catalog root, URL-encoded) on its
second conversation, and the address bar keeps up as you change
tabs or pick another read, so it can be copied at any point.
`&conv=<id>` names a conversation by its recording's name instead
of its position. Corrections are saved to
`feedback.yml` beside the recordings, in the format
`agents7 chat-feedback` reads, so the rules to change, the eval rows
and the report all come off the same file. The page is an editor for
it, never a second store.

## Run locally (no Docker)

The default workflow. Needs a local Ollama plus `uv` and `pnpm` (via
corepack). No environment configuration is required to run against Ollama
— the defaults point the backend at `localhost:11434` and at the
repository's `catalog/` folder. The UI ships no agents. It lists two
kinds:

- **Installed agent packages.** A package that declares its config in
  the `agents7.agents` entry point group is listed once it is installed
  into the backend's environment, wherever it was installed from. For
  example, the public sentiment classifier:

  ```bash
  uv pip install --python backend/.venv/bin/python \
      "sentiment-classifier @ git+https://github.com/carlospinto4p/sentiment_classifier@v0.1.0"
  ```

  Its framework tag must match the one `backend/pyproject.toml` pins.
  A `uv sync` on the backend removes it; install it again afterwards.
- **Loose configs in a folder.** The `catalog/` folder is git-ignored
  and empty until you put agent configs in it (the framework's
  `samples/` folder is a good start). To serve a catalog kept
  elsewhere, set `CATALOG_PATH` to its folder.

The framework is a tagged release, pinned in
`backend/pyproject.toml`. To try an unreleased framework change, run
`uv pip install -e <framework checkout>` in `backend/`; the next
`uv sync` puts the tag back. Anything you do put in `.env` (provider keys, ports) is read on
startup; see [Configuration](#configuration).

1. **Ollama** — run it on the host on its default port:

   ```bash
   ollama serve            # or: systemctl start ollama
   ```

2. **Catalog packages** — only for agents that ship as packages.
   Configs that use only the framework's own models and tools need
   nothing installed. Install every such agent into the backend's venv:

   ```bash
   CATALOG_PATH=/path/to/your/catalog \
       uv run --project backend python scripts/install_catalog.py
   ```

   Those agents resolve their `output_model` / `tools` by dotted path
   (e.g. `my_agent.models.MyModel`), so the Run and Eval pages can
   only build them once the package is importable here. The script
   installs each package editable and `--no-deps`, then its
   third-party dependencies.

   **Re-run it after adding a new catalog agent, and after any
   `uv sync` on the backend** — a sync uninstalls them. They are not
   backend dependencies on purpose: each catalog agent is an
   independent package with its own version and venv, so naming them
   here would couple the UI to the catalog. The script discovers them
   instead. The Compose stack serves the `catalog/` folder, and only
   agents that need no package.

   Skipping the step is not silent. Running or evaluating an agent
   whose package is missing answers `422` with the module it could
   not import and the command above, rather than failing with a
   `ModuleNotFoundError` traceback.

3. **Backend** — port 8002 (the dev frontend proxies `/api` to it):

   ```bash
   cd backend
   uv run uvicorn main:app --port 8002 --reload
   ```

4. **Frontend** — Vite dev server on :5186, proxies `/api` → :8002:

   ```bash
   corepack pnpm --dir frontend install
   corepack pnpm --dir frontend dev
   ```

5. Open <http://localhost:5186>.

## Run with Docker Compose

```bash
docker compose up -d --build      # frontend on http://localhost:5185
```

The frontend's published host port defaults to `5185` (a fixed port, not
the common `8080` default). Override it with `FRONTEND_PORT`
in `.env` — the `CORS_ORIGINS` default and the startup banner both follow
that value.

The backend container reaches Ollama via `host.docker.internal`. A
container cannot reach the host's `localhost`, so the host Ollama must bind
a non-loopback address. Binding `0.0.0.0` is the simplest option and serves
**both** the native (`localhost`) and Compose (`host.docker.internal`)
paths at the same time — no switching between them:

```ini
# sudo systemctl edit ollama
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

`0.0.0.0` listens on all host interfaces. On a firewalled dev box that is
fine; otherwise block port 11434 on external interfaces with a firewall
rule (no Ollama or Docker change needed).

## Tests

Backend (pytest, from `backend/`):

```bash
uv run pytest tests/ -v
```

Frontend end-to-end (Playwright, from `frontend/`):

```bash
corepack pnpm exec playwright install chromium   # first run on a machine
corepack pnpm run test:e2e
```

The e2e specs need **no backend**: every `/api` call is stubbed in
`e2e/_helpers.js`, and Playwright starts the Vite dev server itself
(reusing one already running on port 5186).

## Configuration

See [`.env.example`](.env.example) for all environment variables
(`OLLAMA_HOST`, `CORS_ORIGINS`, `API_KEY`, provider keys, tuning). Copy it
to `.env`; secrets never belong in `docker-compose.yml`.

Both ways of starting the backend read that one file. Compose hands it to
the container through `env_file:`; a direct `uv run uvicorn main:app`
loads it in `backend/env_setup.py`. So a provider key set in `.env` makes
that provider usable on the Chatter page either way — before v0.30.1 it
worked only under Compose.

A real environment variable always wins over the file, which keeps the
values `docker-compose.yml` sets in `environment:` — and an explicit
`VAR=... uv run uvicorn ...` — in charge.

## Logs

The **backend** writes its own `WARNING` and `ERROR`/`CRITICAL` records to
level-segregated folders, one file per process start (rotated by size):

```
logs/
  warnings/   # WARNING records only
  errors/     # ERROR and CRITICAL records
```

In the Compose stack the backend's `LOGS_DIR=/app` is bind-mounted to
`logs/` on the host. Running locally, files land under
`backend/logs/`. The folder is gitignored.

Scope: these folders hold **first-party backend code's** warnings and
errors only. The frontend is nginx (third-party) — use
`docker compose logs frontend` for it.
