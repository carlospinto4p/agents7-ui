
# Backlog - agents7 UI

### Catalog — 23rd August 2026

- [ ] `backend/routers/catalog.py` caches the list of discovered `config.yml`
  paths in `_catalog_cache` on first request and never rebuilds it, so a newly
  added agent folder only appears after a backend restart. Config *edits* are
  picked up live (`_load_config` re-reads on every request) — it is only new
  folders that go missing. Add a refresh path, or drop the path cache (an
  `rglob` over the catalog is cheap). (LOW, S)

### Config — 12th July 2026

- [ ] Set `ANTHROPIC_API_KEY` in `agents7_ui/.env` so the Chatter page's
  Anthropic provider override can be used. Until set, Anthropic shows as
  "not ready" on the Chatter page. `OPENAI_COMPAT_API_KEY` is set (DeepSeek,
  23rd August 2026). (LOW, S)
