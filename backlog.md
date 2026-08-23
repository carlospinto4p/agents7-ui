
# Backlog - agents7 UI

### Local dev — 23rd August 2026

- [ ] Running the backend locally without Docker (`uv run uvicorn main:app` from `agents7_ui/backend/`) cannot execute any catalog agent that is its own installable package with a dotted `output_model`/`tools` path outside the framework — e.g. `POST /api/run/Tagger agent` fails with `ModuleNotFoundError: No module named 'tagger_agent'`, because the backend's own `.venv` never has that package installed. `Dockerfile.backend` already works around this for the Compose stack by `uv pip install --system --no-deps` on every `agents_catalog/*/pyproject.toml` package, but the README's "Run locally (no Docker)" section doesn't mention doing the same for a local venv. Either document a `uv pip install --no-deps -e agents_catalog/tagger_agent` step for local dev, or add a small dev script that does it for every catalog package. (HIGH, S — found while testing `StoreAssistant`'s Runner; `StoreAssistant` itself no longer hits this after being moved to `agents_catalog/examples/`, since its tools now resolve to `agents7.tools.demo`, which the backend already depends on.)

### Config — 12th July 2026

- [ ] Set the provider API keys in `agents7_ui/.env` so the Chatter page's provider override can use them: `ANTHROPIC_API_KEY` (Anthropic) and `OPENAI_COMPAT_API_KEY` or `OPENAI_API_KEY` (openai_compat). Until set, those providers show as "not ready" on the Chatter page. (LOW, S)

