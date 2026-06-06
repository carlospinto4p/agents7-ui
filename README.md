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

## Configuration

See [`.env.example`](.env.example) for all environment variables
(`OLLAMA_HOST`, `CORS_ORIGINS`, `API_KEY`, provider keys, tuning). Copy it
to `.env` for the Compose stack; secrets never belong in `docker-compose.yml`.
