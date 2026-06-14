
# Backlog - agents7 UI

### Improvements — 14th June 2026

- [ ] Display `cost_cents` in the run/chat/eval metrics panels — the backend already returns it (`run.py`), but the frontend never renders it. Easy, high-signal win. (MED, S)
- [ ] Export & copy — download JSON for run output / eval results / chat transcript, plus copy-to-clipboard buttons on the JSON output and YAML source blocks. (MED, S)
- [ ] Catalog search/filter box — the frontend loads all agents at once with no way to filter by name, type, or provider/model; will not scale as the catalog grows. (MED, S)
