# agents7 UI

Web UI for the agents7 framework and catalog: browse agents, run them,
chat, evaluate, and inspect the Ollama engine. FastAPI backend + Svelte
(Vite) frontend.

## Run locally (no Docker)

The default workflow. Needs a local Ollama plus `uv` and `pnpm` (via
corepack). No environment configuration is required — the defaults point
the backend at `localhost:11434` and the repo's `agents_catalog/`.

1. **Ollama** — run it on the host on its default port:

   ```bash
   ollama serve            # or: systemctl start ollama
   ```

2. **Backend** — port 8001 (the dev frontend proxies `/api` to it):

   ```bash
   cd agents7_ui/backend
   uv run uvicorn main:app --port 8001 --reload
   ```

3. **Frontend** — Vite dev server on :5173, proxies `/api` → :8001:

   ```bash
   corepack pnpm --dir agents7_ui/frontend install
   corepack pnpm --dir agents7_ui/frontend dev
   ```

4. Open <http://localhost:5173>.

## Run with Docker Compose

```bash
docker compose up -d --build      # frontend on http://localhost:8080
```

The backend container reaches Ollama via `host.docker.internal`. Because
the host Ollama binds `localhost` by default — which containers cannot
reach — using this stack requires rebinding the host service to a
docker-reachable address, e.g. in its systemd unit:

```ini
# sudo systemctl edit ollama
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

`0.0.0.0` exposes Ollama on all host interfaces; scope it tighter (e.g. a
docker bridge IP) if the box isn't firewalled. This is only needed for the
Compose path — the local workflow above leaves Ollama on `localhost`.

## Configuration

See [`.env.example`](.env.example) for all environment variables
(`OLLAMA_HOST`, `CORS_ORIGINS`, `API_KEY`, provider keys, tuning). Copy it
to `.env` for the Compose stack; secrets never belong in `docker-compose.yml`.
