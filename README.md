# agents7 UI

Web UI for the agents7 framework and catalog: browse agents, run them,
chat, evaluate, and inspect the Ollama engine. FastAPI backend + Svelte
(Vite) frontend.

## Run locally (no Docker)

The default workflow. Needs a local Ollama plus `uv` and `pnpm` (via
corepack). No environment configuration is required to run against Ollama
— the defaults point the backend at `localhost:11434` and the repo's
`agents_catalog/`. Anything you do put in `.env` (provider keys, ports) is
read on startup; see [Configuration](#configuration).

1. **Ollama** — run it on the host on its default port:

   ```bash
   ollama serve            # or: systemctl start ollama
   ```

2. **Catalog packages** — install every catalog agent that ships as a
   package into the backend's venv:

   ```bash
   uv run --project agents7_ui/backend python agents7_ui/scripts/install_catalog.py
   ```

   Those agents resolve their `output_model` / `tools` by dotted path
   (e.g. `tagger_agent.models.NickTag`), so without this step
   `POST /api/run/Tagger agent` fails with `ModuleNotFoundError`. The
   script installs each package editable and `--no-deps`, then its
   third-party dependencies. Re-run it after adding a new catalog
   package, and after any `uv sync` on the backend — the catalog
   packages are not backend dependencies, so a sync uninstalls them.
   The Compose stack does the same thing in `Dockerfile.backend` and
   needs no manual step.

3. **Backend** — port 8002 (the dev frontend proxies `/api` to it):

   ```bash
   cd agents7_ui/backend
   uv run uvicorn main:app --port 8002 --reload
   ```

4. **Frontend** — Vite dev server on :5186, proxies `/api` → :8002:

   ```bash
   corepack pnpm --dir agents7_ui/frontend install
   corepack pnpm --dir agents7_ui/frontend dev
   ```

5. Open <http://localhost:5186>.

## Run with Docker Compose

```bash
docker compose up -d --build      # frontend on http://localhost:5185
```

The frontend's published host port defaults to `5185` (a registry-claimed
port, never the shared `8080` default). Override it with `FRONTEND_PORT`
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
`agents7_ui/logs/` on the host. Running locally, files land under
`backend/logs/`. The folder is gitignored.

Scope: these folders hold **first-party backend code's** warnings and
errors only. The frontend is nginx (third-party) — use
`docker compose logs frontend` for it.
