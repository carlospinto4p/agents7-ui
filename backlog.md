
# Backlog - agents7 UI

### Config — 12th July 2026

- [ ] Set `ANTHROPIC_API_KEY` in `agents7_ui/.env` so the Chatter page's
  Anthropic provider override can be used. Until set, Anthropic shows as
  "not ready" on the Chatter page. `OPENAI_COMPAT_API_KEY` is set (DeepSeek,
  23rd August 2026). (LOW, S)
- [ ] `agents7_ui/.env` reaches the app only through the Compose stack's
  `env_file:` — nothing in `backend/` loads it, so the "Run locally (no
  Docker)" workflow (`uv run uvicorn main:app`) starts with none of those
  variables and the Chatter page reports every non-Ollama provider as "not
  ready" even when the keys are present in the file. Either load the file in
  `backend/main.py` (e.g. `python-dotenv`, pointed at `../.env`, without
  overriding real environment variables) or document exporting the variables
  in the README's local-dev section. (MED, S — found 23rd August 2026 while
  checking provider readiness after a DeepSeek key was added.)
