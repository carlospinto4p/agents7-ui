
# Backlog - agents7 UI

### Improvements — 14th June 2026

- [x] Token-by-token streaming for the chat UI via SSE — the framework already exposes `chat_stream` / `chat_stream_async`, but the backend returns whole responses, so chat feels laggy on long replies. Stream chunks to `ChatPanel.svelte`. (HIGH, M)
- [ ] Display `cost_cents` in the run/chat/eval metrics panels — the backend already returns it (`run.py`), but the frontend never renders it. Easy, high-signal win. (MED, S)
- [ ] Export & copy — download JSON for run output / eval results / chat transcript, plus copy-to-clipboard buttons on the JSON output and YAML source blocks. (MED, S)
- [ ] Catalog search/filter box — the frontend loads all agents at once with no way to filter by name, type, or provider/model; will not scale as the catalog grows. (MED, S)


### Scan findings — 2026.06.07

Test coverage:

- [x] `import_class` and `_load_output_schema` error paths untested (`backend/routers/utils.py`) — missing module/class, malformed dotted path, ImportError/AttributeError suppression. (LOW, S)
