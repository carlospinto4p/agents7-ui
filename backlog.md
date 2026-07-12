
# Backlog - agents7 UI

### Config — 12th July 2026

- [ ] Set the provider API keys in `agents7_ui/.env` so the Chatter page's provider override can use them: `ANTHROPIC_API_KEY` (Anthropic) and `OPENAI_COMPAT_API_KEY` or `OPENAI_API_KEY` (openai_compat). Until set, those providers show as "not ready" on the Chatter page. (LOW, S)

### Testing — 12th July 2026

- [ ] Bootstrap a frontend test harness (Playwright e2e). The frontend has no automated tests, so interactive/render features ship verified only by build + manual check. First candidate to cover: sidebar drag-to-resize + width persistence added in v0.22.0. (MED, M)
