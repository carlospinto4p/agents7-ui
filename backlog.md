
# Backlog - agents7 UI

### Scan — 17th May 2026

#### Performance

- [x] Cache `CATALOG_PATH.rglob()` results in `catalog.py` — `find_config_file()` (line 57) and `list_agents()` (line 69) each scan the full tree; build a name-to-path index on startup instead (HIGH, M)
- [x] Create a module-level `httpx.AsyncClient` in `routers/engine.py:16` to reuse connection pool across requests (MED, M)
- [ ] Replace triple `.filter()` in `Runner.svelte:196-198` with a single-pass `$derived` for `passCount`/`failCount`/`doneCount` (MED, S)
- [ ] Replace triple `.filter()` in `Catalog.svelte:8-12` with single-pass `reduce()` for agent grouping (LOW, S)
- [ ] Fix multi-pass text parsing in `Runner.svelte:110-122` `parseLines()` — use single-pass JSONL parser (LOW, S)

#### Refactoring

- [ ] Verify `Chatter.svelte:18-30` `$effect` — agents found hidden reactive dependency on `agentName`/`starting`; v0.8.14 may have only partially fixed it. Audit with `untrack()` or move to explicit event handler (HIGH, S)
- [ ] Verify `Runner.svelte:37-46` and `Eval.svelte:8-16` for similar untracked `$effect` dependency on fetch — add explicit deps or `untrack()` (MED, S)
- [ ] Extract duplicate agent type maps in `routers/run.py:6-11` and `routers/chat.py:17-23` into shared util (MED, S)
- [ ] Extract session storage dicts in `routers/chat.py:26-31` (`_sessions`, `_session_times`, `_start_counts`) into a `SessionStore` class (MED, M)
- [ ] Standardize error handling across routers — some raise `ValueError`, others `HTTPException` for same scenarios (MED, M)
- [ ] Extract config loading (`yaml.safe_load` + `from_yaml()`) duplicated in `run.py:81-82` and `chat.py:68-69` (LOW, S)
